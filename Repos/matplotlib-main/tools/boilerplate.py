"""
Script to autogenerate pyplot wrappers.

When this script is run, the current contents of pyplot are
split into generatable and non-generatable content (via the magic header
:attr:`PYPLOT_MAGIC_HEADER`) and the generatable content is overwritten.
Hence, the non-generatable content should be edited in the pyplot.py file
itself, whereas the generatable content must be edited via templates in
this file.
"""

# Although it is possible to dynamically generate the pyplot functions at
# runtime with the proper signatures, a static pyplot.py is simpler for static
# analysis tools to parse.

from enum import Enum
import inspect
from inspect import Parameter
from pathlib import Path
import sys
import textwrap

# This line imports the installed copy of matplotlib, and not the local copy.
import numpy as np
from matplotlib import _api, mlab
from matplotlib.axes import Axes
from matplotlib.backend_bases import MouseButton
from matplotlib.figure import Figure


# we need to define a custom str because py310 change
# In Python 3.10 the repr and str representation of Enums changed from
#
#  str: 'ClassName.NAME' -> 'NAME'
#  repr: '<ClassName.NAME: value>' -> 'ClassName.NAME'
#
# which is more consistent with what str/repr should do, however this breaks
# boilerplate which needs to get the ClassName.NAME version in all versions of
# Python. Thus, we locally monkey patch our preferred str representation in
# here.
#
# bpo-40066
# https://github.com/python/cpython/pull/22392/
def enum_str_back_compat_patch(self):
    return f'{type(self).__name__}.{self.name}'

# only monkey patch if we have to.
if str(MouseButton.LEFT) != 'MouseButton.Left':
    MouseButton.__str__ = enum_str_back_compat_patch


# This is the magic line that must exist in pyplot, after which the boilerplate
# content will be appended.
PYPLOT_MAGIC_HEADER = (
    "################# REMAINING CONTENT GENERATED BY boilerplate.py "
    "##############\n")

AUTOGEN_MSG = """

# Autogenerated by boilerplate.py.  Do not edit as changes will be lost."""

AXES_CMAPPABLE_METHOD_TEMPLATE = AUTOGEN_MSG + """
@_copy_docstring_and_deprecators(Axes.{called_name})
def {name}{signature}:
    __ret = gca().{called_name}{call}
    {sci_command}
    return __ret
"""

AXES_METHOD_TEMPLATE = AUTOGEN_MSG + """
@_copy_docstring_and_deprecators(Axes.{called_name})
def {name}{signature}:
    return gca().{called_name}{call}
"""

FIGURE_METHOD_TEMPLATE = AUTOGEN_MSG + """
@_copy_docstring_and_deprecators(Figure.{called_name})
def {name}{signature}:
    return gcf().{called_name}{call}
"""

CMAP_TEMPLATE = '''
def {name}():
    """
    Set the colormap to {name!r}.

    This changes the default colormap as well as the colormap of the current
    image if there is one. See ``help(colormaps)`` for more information.
    """
    set_cmap({name!r})
'''  # Colormap functions.


class value_formatter:
    """
    Format function default values as needed for inspect.formatargspec.
    The interesting part is a hard-coded list of functions used
    as defaults in pyplot methods.
    """

    def __init__(self, value):
        if value is mlab.detrend_none:
            self._repr = "mlab.detrend_none"
        elif value is mlab.window_hanning:
            self._repr = "mlab.window_hanning"
        elif value is np.mean:
            self._repr = "np.mean"
        elif value is _api.deprecation._deprecated_parameter:
            self._repr = "_api.deprecation._deprecated_parameter"
        elif isinstance(value, Enum):
            # Enum str is Class.Name whereas their repr is <Class.Name: value>.
            self._repr = str(value)
        else:
            self._repr = repr(value)

    def __repr__(self):
        return self._repr


def generate_function(name, called_fullname, template, **kwargs):
    """
    Create a wrapper function *pyplot_name* calling *call_name*.

    Parameters
    ----------
    name : str
        The function to be created.
    called_fullname : str
        The method to be wrapped in the format ``"Class.method"``.
    template : str
        The template to be used. The template must contain {}-style format
        placeholders. The following placeholders are filled in:

        - name: The function name.
        - signature: The function signature (including parentheses).
        - called_name: The name of the called function.
        - call: Parameters passed to *called_name* (including parentheses).

    **kwargs
        Additional parameters are passed to ``template.format()``.
    """
    text_wrapper = textwrap.TextWrapper(
        break_long_words=False, width=70,
        initial_indent=' ' * 8, subsequent_indent=' ' * 8)

    # Get signature of wrapped function.
    class_name, called_name = called_fullname.split('.')
    class_ = {'Axes': Axes, 'Figure': Figure}[class_name]

    meth = getattr(class_, called_name)
    decorator = _api.deprecation.DECORATORS.get(meth)
    # Generate the wrapper with the non-kwonly signature, as it will get
    # redecorated with make_keyword_only by _copy_docstring_and_deprecators.
    if decorator and decorator.func is _api.make_keyword_only:
        meth = meth.__wrapped__
    signature = inspect.signature(meth)
    # Replace self argument.
    params = list(signature.parameters.values())[1:]
    signature = str(signature.replace(parameters=[
        param.replace(default=value_formatter(param.default))
        if param.default is not param.empty else param
        for param in params]))
    if len('def ' + name + signature) >= 80:
        # Move opening parenthesis before newline.
        signature = '(\n' + text_wrapper.fill(signature).replace('(', '', 1)
    # How to call the wrapped function.
    call = '(' + ', '.join((
           # Pass "intended-as-positional" parameters positionally to avoid
           # forcing third-party subclasses to reproduce the parameter names.
           '{0}'
           if param.kind in [
               Parameter.POSITIONAL_OR_KEYWORD]
              and param.default is Parameter.empty else
           # Only pass the data kwarg if it is actually set, to avoid forcing
           # third-party subclasses to support it.
           '**({{"data": data}} if data is not None else {{}})'
           # Avoid linebreaks in the middle of the expression, by using \0 as a
           # placeholder that will be substituted after wrapping.
           .replace(' ', '\0')
           if param.name == "data" else
           '{0}={0}'
           if param.kind in [
               Parameter.POSITIONAL_OR_KEYWORD,
               Parameter.KEYWORD_ONLY] else
           '{0}'
           if param.kind is Parameter.POSITIONAL_ONLY else
           '*{0}'
           if param.kind is Parameter.VAR_POSITIONAL else
           '**{0}'
           if param.kind is Parameter.VAR_KEYWORD else
           None).format(param.name)
       for param in params) + ')'
    MAX_CALL_PREFIX = 18  # len('    __ret = gca().')
    if MAX_CALL_PREFIX + max(len(name), len(called_name)) + len(call) >= 80:
        call = '(\n' + text_wrapper.fill(call[1:]).replace('\0', ' ')
    # Bail out in case of name collision.
    for reserved in ('gca', 'gci', 'gcf', '__ret'):
        if reserved in params:
            raise ValueError(
                f'Method {called_fullname} has kwarg named {reserved}')

    return template.format(
        name=name,
        called_name=called_name,
        signature=signature,
        call=call,
        **kwargs)


def boilerplate_gen():
    """Generator of lines for the automated part of pyplot."""

    _figure_commands = (
        'figimage',
        'figtext:text',
        'gca',
        'gci:_gci',
        'ginput',
        'subplots_adjust',
        'suptitle',
        'tight_layout',
        'waitforbuttonpress',
    )

    # These methods are all simple wrappers of Axes methods by the same name.
    _axes_commands = (
        'acorr',
        'angle_spectrum',
        'annotate',
        'arrow',
        'autoscale',
        'axhline',
        'axhspan',
        'axis',
        'axline',
        'axvline',
        'axvspan',
        'bar',
        'barbs',
        'barh',
        'bar_label',
        'boxplot',
        'broken_barh',
        'clabel',
        'cohere',
        'contour',
        'contourf',
        'csd',
        'errorbar',
        'eventplot',
        'fill',
        'fill_between',
        'fill_betweenx',
        'grid',
        'hexbin',
        'hist',
        'stairs',
        'hist2d',
        'hlines',
        'imshow',
        'legend',
        'locator_params',
        'loglog',
        'magnitude_spectrum',
        'margins',
        'minorticks_off',
        'minorticks_on',
        'pcolor',
        'pcolormesh',
        'phase_spectrum',
        'pie',
        'plot',
        'plot_date',
        'psd',
        'quiver',
        'quiverkey',
        'scatter',
        'semilogx',
        'semilogy',
        'specgram',
        'spy',
        'stackplot',
        'stem',
        'step',
        'streamplot',
        'table',
        'text',
        'tick_params',
        'ticklabel_format',
        'tricontour',
        'tricontourf',
        'tripcolor',
        'triplot',
        'violinplot',
        'vlines',
        'xcorr',
        # pyplot name : real name
        'sci:_sci',
        'title:set_title',
        'xlabel:set_xlabel',
        'ylabel:set_ylabel',
        'xscale:set_xscale',
        'yscale:set_yscale',
    )

    cmappable = {
        'contour': 'if __ret._A is not None: sci(__ret)  # noqa',
        'contourf': 'if __ret._A is not None: sci(__ret)  # noqa',
        'hexbin': 'sci(__ret)',
        'scatter': 'sci(__ret)',
        'pcolor': 'sci(__ret)',
        'pcolormesh': 'sci(__ret)',
        'hist2d': 'sci(__ret[-1])',
        'imshow': 'sci(__ret)',
        'spy': 'if isinstance(__ret, cm.ScalarMappable): sci(__ret)  # noqa',
        'quiver': 'sci(__ret)',
        'specgram': 'sci(__ret[-1])',
        'streamplot': 'sci(__ret.lines)',
        'tricontour': 'if __ret._A is not None: sci(__ret)  # noqa',
        'tricontourf': 'if __ret._A is not None: sci(__ret)  # noqa',
        'tripcolor': 'sci(__ret)',
    }

    for spec in _figure_commands:
        if ':' in spec:
            name, called_name = spec.split(':')
        else:
            name = called_name = spec
        yield generate_function(name, f'Figure.{called_name}',
                                FIGURE_METHOD_TEMPLATE)

    for spec in _axes_commands:
        if ':' in spec:
            name, called_name = spec.split(':')
        else:
            name = called_name = spec

        template = (AXES_CMAPPABLE_METHOD_TEMPLATE if name in cmappable else
                    AXES_METHOD_TEMPLATE)
        yield generate_function(name, f'Axes.{called_name}', template,
                                sci_command=cmappable.get(name))

    cmaps = (
        'autumn',
        'bone',
        'cool',
        'copper',
        'flag',
        'gray',
        'hot',
        'hsv',
        'jet',
        'pink',
        'prism',
        'spring',
        'summer',
        'winter',
        'magma',
        'inferno',
        'plasma',
        'viridis',
        "nipy_spectral"
    )
    # add all the colormaps (autumn, hsv, ....)
    for name in cmaps:
        yield AUTOGEN_MSG
        yield CMAP_TEMPLATE.format(name=name)


def build_pyplot(pyplot_path):
    pyplot_orig = pyplot_path.read_text().splitlines(keepends=True)
    try:
        pyplot_orig = pyplot_orig[:pyplot_orig.index(PYPLOT_MAGIC_HEADER) + 1]
    except IndexError as err:
        raise ValueError('The pyplot.py file *must* have the exact line: %s'
                         % PYPLOT_MAGIC_HEADER) from err

    with pyplot_path.open('w') as pyplot:
        pyplot.writelines(pyplot_orig)
        pyplot.writelines(boilerplate_gen())


if __name__ == '__main__':
    # Write the matplotlib.pyplot file.
    if len(sys.argv) > 1:
        pyplot_path = Path(sys.argv[1])
    else:
        pyplot_path = Path(__file__).parent / "../lib/matplotlib/pyplot.py"
    build_pyplot(pyplot_path)