# Import standard Python modules.
import ast, operator
import re

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
