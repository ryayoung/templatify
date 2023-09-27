from typing import Callable, Any
import inspect
from jinja2 import Environment
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
        return generate_template_function(func, render_func, param_defaults)

    if callable(__func):
        return decorator(__func)
    return decorator


def generate_template_function(
    original_func: Callable,
    render_func: Callable,
    param_defaults: dict,
):
    """
    Dynamically generates a function with the same parameters (names, AND values)
    as `original_func`. The implementation simply passes them to `render_func`.
    """
    define_param = lambda name, default: (
        name if default_is_empty(default) else f"{name}=_defaults_['{name}']"
    )
    params_definition = ", ".join(define_param(k, v) for k, v in param_defaults.items())
    arguments_str = ", ".join(f"{name}={name}" for name in param_defaults)

    func_name = "wrapper"
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


def default_is_empty(default: Any) -> bool:
    """
    Determines whether the parameter whose default is `default` is a required
    parameter or not.
    This function exists because some objects (e.g. pandas.DataFrame)
    raise an exception when you try to check equality as a boolean.
    """
    try:
        return bool(default == inspect.Parameter.empty)
    except Exception:
        return False


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
