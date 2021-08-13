#!/usr/bin/python3

import re
import os
import sys
from argparse import ArgumentParser, SUPPRESS

from sd.common import list_get, DotDict
from sd.columns import auto_cols, undent


def easy_parse(optionals_list, pos_list=None, **kargs):
    '''
    Simpler way to pass arguments to ArgMaster class.
    All kargs are passed to ArgMaster. See the actual implementation for details.
    '''
    am = ArgMaster(**kargs)
    if pos_list:
        am.update(pos_list, title="Positional Arguments", positionals=True)
    am.update(optionals_list, title="Optional Arguments")
    return am.parse(argfixer())


class ArgMaster():
    '''
    A wrapper class for ArgumentParser with easy to use arguments. See update_parser() for details.
    sortme will sort all arguments by name (except positionals)
    other arguments are passed onto the ArgumentParser constructor
    '''

    def __init__(self, sortme=True, allow_abbrev=True, usage=None, description=None, newline='\n',
                 verbose=False, **kargs):
        self.sortme = sortme            # Sort all non positionals args
        self.groups = []                # List of all groups
        self.usage = usage              # Usage message
        self.verbose = verbose
        self.newline = newline          # Newlines in print_help
        self.description = description
        self.parser = ArgumentParser(allow_abbrev=allow_abbrev, add_help=False, usage=SUPPRESS, **kargs)
        # Allow optionals before positionals:
        self.intermixed = hasattr(self.parser, 'parse_intermixed_args')

    def update(self, args, title=None, sortme=None, **kargs):
        group = self.parser.add_argument_group(title)
        args = update_parser(args, group, verbose=self.verbose, **kargs)
        self.groups.append(DotDict(args=args, title=title, sortme=sortme))

    def parse(self, args=None, am_help=True, **kargs):
        if not args:
            args = sys.argv[1:]

        if not am_help:
            self.parser.add_help = True
            return self.parser.parse_args(args)

        # Match help
        for arg in args:
            if re.match('--*h$|--*help$', arg):
                self.print_help(**kargs)
                sys.exit(0)
        try:
            if self.intermixed:
                return self.parser.parse_intermixed_args(args)
            else:
                return self.parser.parse_args(args)
        except SystemExit:
            self.print_help(**kargs)
            sys.exit(0)


    def print_help(self, show_type=True, wrap=-4, tab='  '):
        '''Print a custom help message using only ArgMaster args
        show_type = append the variable type expected after each optional argument.
        --arg <int> <int> will expect 2 integers after the arg
        wrap = word wrap instead of using full terminal. 0 = Terminal width
        sort = sort alphabetically. Positional variables are never sorted.
        To sort individual groups, add a special key: group.sortme = True

        Warning: If your variable is not in a group, it will not be shown!'''

        if self.description:
            print('\n' + self.description)

        if self.usage:
            name = os.path.basename(sys.argv[0])
            print('\n' + "Usage:", name, self.usage)
        final = []
        width = 0                       # Max width of the variables column
        for group in self.groups:
            out = []
            for args in group.args:
                args = DotDict(args)
                msg = args.msg
                if msg == SUPPRESS:
                    continue
                alias = args.alias
                if show_type:
                    if args.typ and args.typ != bool:
                        if args.typ == list:
                            typ = '...'
                        else:
                            typ = '<' + str(args.typ).replace('class ', '')[2:-2] + '>'
                        alias += ' ' + typ
                if len(alias) > width:
                    width = len(alias)
                out.append([alias, msg])

            if group.sortme is not None:
                sortme = group.sortme
            else:
                sortme = self.sortme
            if sortme:
                # Sort the group while mainting the order of positional arguments at the top
                positionals = [out.pop(line) for line in range(len(out) - 1, -1, -1) if out[line][0].startswith('<')]
                out.sort()
                out = list(reversed(positionals)) + out
            final.append(out)

        for index, out in enumerate(final):
            group = self.groups[index]
            if out:
                print(self.newline, end='')
                for line, _ in enumerate(out):
                    out[line][0] = tab + out[line][0].ljust(width)
                if group.title:
                    print(group.title)  # .rstrip(':') + ':')
                if group.description:
                    auto_cols([[tab + group.description]], wrap=wrap)
                auto_cols(out, wrap=wrap)
        print()


def argfixer():
    '''Fix up args for argparse. Lowers case and turns -args into --args'''
    out = []
    for word in sys.argv:
        if word.startswith('-'):
            word = word.lower()
        if re.match('^-[^-]', word):
            out.append('-' + word)
        else:
            out.append(word)
    return out[1:]


def update_parser(lines, parser=None, hidden=False, positionals=False, verbose=False):
    '''
    This is a more intuitive method for adding optional arguments.

        Example:

        basic_args = [\
        ('alias', 'variable_name', type, default),
        "help string",
        ...
        ]

        group_basic = parser.add_argument_group('Basic Arguments', '')
        update_parser(basic_args, group_basic)

    You only need to include the arguments required, but you can't skip over any.
        ('alias', '',)        # okay
        ('alias', type,)      # not okay

    Substitute the word list with a number like "2" to get that number of args required.
        ('list-args, '', 2)

    Positional arguments are optional by default, but you can specify a number to make them required.
    To use them, make sure to pass: positionals=True to update_parser

        ('pos-arg', '', 1)

    See what your arguments are producing by passing verbose=True or by doing:
        auto_cols(sorted([[key, repr(val)] for key, val in (vars(parse_args())).items()]))


    '''

    # Make sure the loop ends on a help string
    if not isinstance(lines[-1], str):
        lines.append("")

    alias = None        #
    varname = None      # Variable Name
    default = None      # Default value
    out = []

    def update():
        nonlocal alias
        "# Update argument to parser:"
        if parser:
            if positionals:
                parser.add_argument(varname, default=default, nargs=nargs, help=msg)
            else:
                alias = '--' + alias
                if typ == bool:
                    parser.add_argument(alias, dest=varname, default=default, action=action, help=msg)
                else:
                    parser.add_argument(alias, dest=varname, default=default, type=typ,
                                        nargs=nargs, help=msg, metavar='')
            out.append(dict(alias=alias, dest=varname, typ=typ, default=default, msg=msg))
            if verbose:
                print('alias  :', alias)
                print('dest   :', varname)
                print('default:', default)
                print('type   :', typ)
                print('nargs  :', nargs, '\n\n')

    for index, args in enumerate(lines):

        # Add help if available
        if isinstance(args, str):
            msg = undent(args.strip())
            if msg and not msg.endswith('.'):
                last = msg.split()[-1]
                if last[-1].isalnum() and not last.startswith('-'):
                    msg = msg + '.'
            if default:
                msg += "  Default: " + str(default)

        if hidden:
            # Hide the help text:
            msg = SUPPRESS

        # If on a new tuple line, add_argument
        if alias or varname:
            update()
            alias = None
            varname = None
            msg = ""

        # Continue if not on a new tuple line
        if isinstance(args, str):
            continue

        # Read the values from the tuple:
        alias = args[0].lstrip('-')

        # Variable Name
        varname = list_get(args, 1)
        if not varname:
            varname = alias

        # Argument Type and number required
        default = list_get(args, 3, '')
        typ = list_get(args, 2, type(default))
        if typ == list:
            nargs = '*'
            typ = str
            default = []
        elif isinstance(typ, int):
            if positionals and typ == 1:
                nargs = None
            else:
                nargs = typ
            typ = str
        else:
            nargs = '?'

        # Special handing for booleans
        if typ == bool:
            if default:
                action = 'store_false'
            else:
                action = 'store_true'
                default = False
        if index == len(lines) - 1:
            update()

    return out


def help_parser(parser, show_type=True, sortme=True, wrap=100, tab='  '):
    '''Print a custom help message from the ArgumentParser class
        show_type = append the variable type expected after each optional argument.
        --arg <int> <int> will expect 2 integers after the arg
        wrap = word wrap instead of using full terminal. 0 = disable
        sort = sort alphabetically. Positional variables are never sorted.
        To sort individual groups, add a special key: group.sortme = True

        Warning: If your variable is not in a group, it will not be shown!
    '''
    def alias(action):
        "Return string representing the variable for the leftmost column"
        if action.option_strings:
            text = ', '.join(action.option_strings)
        else:
            text = action.dest
        if show_type:
            if not action.option_strings:
                text = '<' + text + '>'
            if action.type and action.type != bool:
                if action.type == list:
                    typ = '...'
                else:
                    typ = '<' + str(action.type).replace('class ', '')[2:-2] + '>'

                if isinstance(action.nargs, int):
                    count = action.nargs
                else:
                    count = 1
                text += ' ' + ' '.join([typ] * count)
        return text

    final = []
    width = 0
    for group in parser._action_groups:         # pylint: disable=W0212
        out = []
        for action in group._group_actions:     # pylint: disable=W0212
            if action.help and action.help == SUPPRESS:
                continue
            msg = list(action.help)
            msg[0] = msg[0].title()
            variable = alias(action)
            out.append([variable, ''.join(msg)])
            if len(variable) > width:
                width = len(variable)
        if sortme or group.__dict__.get('sortme', False):
            # Sort the group while mainting the order of positional arguments at the top
            positionals = [out.pop(line) for line in range(len(out) - 1, -1, -1) if out[line][0].startswith('<')]
            out.sort()
            out = list(reversed(positionals)) + out
        final.append(out)

    for group in parser._action_groups:         # pylint: disable=W0212
        out = final.pop(0)
        if out:
            for line, _ in enumerate(out):
                out[line][0] = tab + out[line][0].ljust(width)

            print()
            if group.title:
                print(group.title + ':')
            if group.description:
                auto_cols([[tab + group.description]])
            auto_cols(out, wrap=wrap)
