from typing import Callable, Any
import inspect
from jinja2 import Environment
from dataclasses import Field
from jinja2.meta import find_undeclared_variables
from functools import wraps
import textwrap
import builtins

builtin_items = {
    name: getattr(builtins, name) for name in dir(builtins) if not name.startswith("_")
}


class TemplateError(Exception):
    pass


# Note that there are purposefully no type annotations on `template`. We want
# the type checker to enforce the types of the decorated function instead.


def template(
    __func=None,
    /,
    *,
    env: Environment | None = None,
    globals: dict | None = None,
    include_builtins: bool = True,
):
    """
    Decorator to create a template function.

    Parameters
    ----------
    env : jinja2.Environment, optional
        An optional Jinja2 environment to use. If provided, then `globals` and
        `include_builtins` are ignored.
    globals : dict, optional
        A dictionary of variable names/values to be accessible within the template.
        Note that if `include_builtins` is True, then the built-in functions will
        be added first, and then `globals` will be added on top of that.
    include_builtins : bool, default True
        Whether to include the built-in functions and classes available in Python
        before imports (e.g. `str`, `len`, `print`) in the template environment.
        If True and `globals` is provided, the builtins will be added first, and
        then `globals` will be added on top of that.
    """
    env = env or create_environment(globals, include_builtins)

    def decorator(func):
        doc = get_formatted_docstring(func)
        param_defaults = get_validated_func_params(func, env, doc)
        render_func = env.from_string(doc).render

        if any(isinstance(v, Field) for v in param_defaults.values()):
            return generate_template_function_with_fields(
                func, render_func, param_defaults
            )
        return generate_template_function(func, render_func, param_defaults)

    if callable(__func):
        return decorator(__func)
    return decorator


def get_formatted_docstring(func: Callable) -> str:
    doc = func.__doc__
    if doc is None:
        raise TemplateError(f"Template, {func.__name__}() must have a docstring")
    if doc.startswith("\n"):
        doc = doc[1:]
    doc = textwrap.dedent(doc)
    return doc


def create_environment(globals: dict | None, include_builtins: bool) -> Environment:
    """
    Creates a Jinja2 environment with the given globals. If `include_builtins`
    is True, then the environment will also include all the built-in functions
    and classes available in Python before imports. (e.g. `str`, `len`, `print`)
    """
    env = Environment()

    env_globals = builtin_items if include_builtins else {}
    if globals is not None:
        env_globals.update(globals)

    env.globals.update(env_globals)
    return env


def get_validated_func_params(
    func: Callable, env: Environment, template_str: str
) -> dict[str, Any]:
    """
    Returns a dictionary of the parameters of `func` and their default values.
    Returns successfully if all undeclared variables in the template are
    satisfied by the parameters of `func`.
    """
    template_dependencies = find_undeclared_variables(env.parse(template_str))

    params = {k: v.default for k, v in inspect.signature(func).parameters.items()}

    for var in template_dependencies:
        if var not in params:
            raise TemplateError(
                f"Template depends on variable '{var}', but '{func.__name__}' "
                + "does not have a parameter with that name"
            )

    return params


def generate_template_function(
    original_func: Callable,
    render_func: Callable,
    param_defaults: dict,
):
    """
    Dynamically generates a function with the same parameters (names, AND values)
    as `original_func`. The implementation simply passes them to `render_func`.
    """

    def define_param(name: str, default: Any) -> str:
        if default is inspect.Parameter.empty:
            return name
        return f"{name}=_defaults_['{name}']"

    params_definition = ", ".join(define_param(k, v) for k, v in param_defaults.items())
    arguments_str = ", ".join(f"{name}={name}" for name in param_defaults)

    func_name = original_func.__name__
    func_definition = f"""\
@wraps(func)
def {func_name}({params_definition}) -> str:
    return render({arguments_str})
"""

    namespace = {
        "wraps": wraps,
        "func": original_func,
        "render": render_func,
        "_defaults_": param_defaults,
    }
    exec(func_definition, namespace)
    return namespace[func_name]


def generate_template_function_with_fields(
    original_func: Callable,
    render_func: Callable,
    param_defaults: dict,
):
    """
    Used instead of `generate_template_function`, whenever any of the values in
    `param_defaults` are instances of `dataclasses.Field`.
    """
    from dataclasses import MISSING, _MISSING_TYPE

    def define_param(name: str, default: Any) -> str:
        if default is inspect.Parameter.empty:
            return name
        if isinstance(default, Field):
            return f"{name}=_MISSING_TYPE"
        return f"{name}=_defaults_['{name}']"

    def define_argument(name: str, default: Any) -> str:
        if not isinstance(default, Field):
            return name

        if default.default is not MISSING:
            attribute_call = f".default"
        elif default.default_factory is not MISSING:
            attribute_call = f".default_factory()"
        else:
            return "None"

        if default.init is False:
            return f"_defaults_['{name}']{attribute_call}"
        return (
            f"{name} if {name} is not _MISSING_TYPE else"
            + f" _defaults_['{name}']{attribute_call}"
        )

    def is_field_init_false(val) -> bool:
        if isinstance(val, Field):
            return val.init is False
        return False

    param_definitions = [
        define_param(k, v)
        for k, v in param_defaults.items()
        if not is_field_init_false(v)
    ]
    arg_definitions = [
        f"{k}=" + define_argument(k, v) for k, v in param_defaults.items()
    ]

    func_name = original_func.__name__
    func_definition = f"""\
@wraps(func)
def {func_name}({", ".join(param_definitions)}) -> str:
    return render({", ".join(arg_definitions)})
"""

    namespace = {
        "wraps": wraps,
        "func": original_func,
        "render": render_func,
        "_MISSING_TYPE": _MISSING_TYPE,
        "_defaults_": param_defaults,
    }
    exec(func_definition, namespace)
    return namespace[func_name]


if __name__ == "__main__":
    # EXAMPLE 1

    @template
    def greet(name: str, age: int = 10):
        "Hello {{ name|upper }}, you are {{ age }} years old."

    print(greet("John"))  # Hello JOHN, you are 10 years old.

    # EXAMPLE 2

    name = "John"
    age = 10

    @template(globals=locals())
    def greet2():
        "Hello {{ name|upper }}, you are {{ age }} years old."

    print(greet2())  # Hello JOHN, you are 10 years old.

    # EXAMPLE 3
    from dataclasses import field

    @template
    def greet(name: str, age: int = field(default=10, init=False)):
        "Hello {{ name|upper }}, you are {{ age }} years old."

    print(greet("John"))  # Hello JOHN, you are 10 years old.
    # print(greet("John", 10))  # TypeError: greet() takes 1 positional argument but 2 were given
