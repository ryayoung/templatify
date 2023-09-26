# Template

The ultimate tool for creating jinja2 string-based templates in Python.

It's painfully simple, and doesn't do anything you don't expect it to.

It's a **zero-cost**, frictionless abstraction that provides convenience,
static type safety, runtime template argument validation, and enforces
a consistent, declarative programming style, all in less than **50 lines of code**.


```py
# An efficient jinja2 template renderer
@template
def greet_user(name: str, age: int = 10):
    "Hello, {{ name|upper }}! You are {{ age }} years old."

print(greet_user("John"))
```

### Declarative Nature

Before the reader of your code sees the string you defined, they will know
it's a template, and they will know what its dependencies are.

### Static Type Safety

Your type checker will enforce the function signature you've defined.

### Efficiency

All runtime logic, validation, and template creation happens **only at the moment
your function is created**.

**This code will NOT run**:
```py
@template
def greet_user(name: str, age: int = 10):
    "Hello, {{ name|upper }}! You are {{ ageeee }} years old."
```

`@template` guarantees that the parameters of your function match the variables
used in the template, ahead of time. The creation and validation of the jinja2
template happens **only once**. Even the attribute lookup on `Template.render()`
is done in advance, so your calls to `greet_user` are as frictionless as possible.


### Zero-Overhead Runtime Dependency Safety

`@template` will dynamically generate a function that matches the signature of the one you provided.
It will pass the given arguments **directly** to the render function of the template that was *already*
created *and* validated when your function was decorated.

Therefore, `@template` achieves runtime validation that **all variables required by your template must be filled**,
and it does so without any compute cost after your function is created.


### What about indentation?

`@template` will dedent your docstring for you, and remove a single leading newline character if one is present,
before creating the jinja template.
If you don't like this feature, or think it should be able to be disabled, please reach out or raise an issue.

```py
@template
def greet_user(name: str, age: int = 10):
    """
    Hello, {{ name|upper }}! You are {{ age }} years old.
        - Indented bullet
    """

print("Docstring (before):\n" + greet_user.__doc__)
print("Template (after):\n" + greet_user("John"))
```

Output:
```
Docstring (before):

    Hello, {{ name|upper }}! You are {{ age }} years old.
        - Indented bullet
    
Template (after):
Hello, JOHN! You are 10 years old.
    - Indented bullet
```
