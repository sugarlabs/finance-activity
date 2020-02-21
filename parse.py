#!/usr/bin/python3
from gi.repository import Gtk
import locale
import ast
import operator
import re

from gettext import gettext as _

from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon


def evaluate(value):
    try:
        result = locale.atof(value)
        return result
    except:
        pass

    if isinstance(value, str):

        binOps = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }

        try:
            node = ast.parse(value, mode='eval')
        except:
            return None

        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            elif isinstance(node, ast.BinOp):
                return binOps[type(node.op)](_eval(node.left), _eval(node.right))
            elif isinstance(node, ast.Num):
                return node.n
            else:
                return None
            return _eval(node.body)

        value = _eval(node)

    decimals_found = re.findall("\d+\.\d+", str(value))
    integers_found = re.findall("\d+", str(value))

    if decimals_found != []:
        return float(decimals_found[0])
    elif integers_found != []:
        return float(integers_found[0])
    return None


def invalid_value_alert(activity):
    alert = Alert()

    alert.props.title = _('Invalid Value')
    alert.props.msg = _('The expression must be a number (integer or decimal)')

    ok_icon = Icon(icon_name='dialog-ok')
    alert.add_button(Gtk.ResponseType.OK, _('Ok'), ok_icon)
    ok_icon.show()

    alert.connect('response', lambda a, r: activity.remove_alert(a))
    activity.add_alert(alert)
    alert.show()


if __name__ == "__main__":
    tests = [
        ['0', 0.0],
        ['0.55', 0.55],
        ['1', 1.0],
        ['2', 2.0],
        ['-2', -2.0],
        ['2+2', 4.0],
        ['4-2', 2.0],
        ['4*2', 8.0],
        ['4/2', 2.0],
        #  ['4*-4', -4.0],  # TypeError: 
        ['4/2-1', 1.0],
        ['1.5', 1.5],
        ['-1.7', -1.7],
    ]
    for test in tests:
        text, expected = test
        observed = evaluate(text)
        if observed != expected:
            print('fail; %r -> %r instead of %r' % (text, observed, expected))
        else:
            print('pass; %r -> %r' % (text, observed))
