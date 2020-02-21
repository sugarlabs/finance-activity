# Import standard Python modules.
import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk
from gi.repository import Gtk
import ast, operator
import re

from gettext import gettext as _

from sugar3.graphics import style
from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon

def evaluate(value):
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
            return decimals_found[0]
        elif integers_found != []:
            return integers_found[0]
        return None

def _invalid_number_alert(activity):
    alert = Alert()

    alert.props.title = _('Invalid Value')
    alert.props.msg = _('The expression must be a number (integer or decimal)')

    ok_icon = Icon(icon_name='dialog-ok')
    alert.add_button(Gtk.ResponseType.OK, _('Ok'), ok_icon)
    ok_icon.show()

    alert.connect('response', lambda a, r: activity.remove_alert(a))
    activity.add_alert(alert)
    alert.show()
