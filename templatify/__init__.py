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


def template(func):
    doc = get_formatted_docstring(func)
    env = get_environment()
    param_defaults = get_validated_func_params(func, env, doc)

    define_param = lambda name, default: (
        name if default_is_empty(default) else f"{name}=_defaults_['{name}']"
    )
    params_definition = ", ".join(define_param(k, v) for k, v in param_defaults.items())
    arguments_str = ", ".join(f"{name}={name}" for name in param_defaults)

    func_definition = f"""\
@wraps(func)
def wrapper({params_definition}) -> str:
    return render({arguments_str})
"""

    namespace = {
        "wraps": wraps,
        "func": func,
        "render": env.from_string(doc).render,
        "_defaults_": param_defaults,
    }
    exec(func_definition, namespace)
    return namespace["wrapper"]


def get_formatted_docstring(func: Callable) -> str:
    doc = func.__doc__
    assert doc is not None, f"Template, {func.__name__}() must have a docstring"
    if doc.startswith("\n"):
        doc = doc[1:]
    doc = textwrap.dedent(doc)
    return doc


def get_environment() -> Environment:
    env = Environment()
    env.globals.update(builtin_items)
    return env


def get_validated_func_params(func: Callable, env: Environment, template_str: str):
    template_dependencies = find_undeclared_variables(env.parse(template_str))

    params = {k: v.default for k, v in inspect.signature(func).parameters.items()}

    for var in template_dependencies:
        if var not in params:
            raise ValueError(
                f"Template depends on variable '{var}', but '{func.__name__}' "
                + "does not have a parameter with that name"
            )

    return params


def default_is_empty(default: Any) -> bool:
    """
    Need a try catch AND a `bool()`, because some objects (e.g. pd.DataFrame)
    raise an exception when you try to check if they are equal to something
    and use the returned value in a boolean context.
    """
    try:
        return bool(default == inspect.Parameter.empty)
    except Exception:
        return False
