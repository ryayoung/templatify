import inspect
from jinja2 import Template, Environment
from jinja2.meta import find_undeclared_variables
from functools import wraps
import textwrap

def template(func):
    doc = func.__doc__
    assert doc is not None, f"Template, {func.__name__}() must have a docstring"

    if doc.startswith("\n"):
        doc = doc[1:]
    doc = textwrap.dedent(doc)

    template_ = Template(doc)
    template_dependencies = find_undeclared_variables(
        Environment().parse(doc)
    )

    sig = inspect.signature(func)
    param_defaults = {k: v.default for k, v in sig.parameters.items()}
    for var in template_dependencies:
        if var not in param_defaults:
            raise ValueError(
                f"Template depends on variable '{var}', but '{func.__name__}' "
                + "does not have a parameter with that name"
            )

    params_definition = ", ".join([
        name if default == inspect.Parameter.empty else f"{name}=_defaults_['{name}']"
        for name, default in param_defaults.items()
    ])

    arguments_str = ", ".join(f"{name}={name}" for name in param_defaults)

    func_definition = f"""\
@wraps(func)
def wrapper({params_definition}) -> str:
    return render({arguments_str})
"""

    namespace = {
        "wraps": wraps,
        "func": func,
        "render": template_.render,
        "_defaults_": param_defaults,
    }
    exec(func_definition, namespace)
    return namespace['wrapper']
