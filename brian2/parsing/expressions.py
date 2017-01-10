'''
AST parsing based analysis of expressions
'''

import ast

from brian2.core.functions import Function
from brian2.parsing.rendering import NodeRenderer
from brian2.units.fundamentalunits import (Unit, get_unit_fast,
                                           DimensionMismatchError,
                                           have_same_dimensions,
                                           get_dimensions,
                                           get_unit, DIMENSIONLESS,
                                           fail_for_dimension_mismatch)

__all__ = ['is_boolean_expression',
           'parse_expression_dimensions', ]


def is_boolean_expression(expr, variables):
    '''
    Determines if an expression is of boolean type or not
    
    Parameters
    ----------
    
    expr : str
        The expression to test
    variables : dict-like of `Variable`
        The variables used in the expression.

    Returns
    -------
    isbool : bool
        Whether or not the expression is boolean.

    Raises
    ------
    SyntaxError
        If the expression ought to be boolean but is not,
        for example ``x<y and z`` where ``z`` is not a boolean variable.
        
    Notes
    -----
    We test the following cases recursively on the abstract syntax tree:
    
    * The node is a boolean operation. If all the subnodes are boolean
      expressions we return ``True``, otherwise we raise the ``SyntaxError``.
    * The node is a function call, we return ``True`` or ``False`` depending
      on whether the function description has the ``_returns_bool`` attribute
      set.
    * The node is a variable name, we return ``True`` or ``False`` depending
      on whether ``is_boolean`` attribute is set or if the name is ``True`` or
      ``False``.
    * The node is a comparison, we return ``True``.
    * The node is a unary operation, we return ``True`` if the operation is
      ``not``, otherwise ``False``.
    * Otherwise we return ``False``.
    '''

    # If we are working on a string, convert to the top level node    
    if isinstance(expr, str):
        mod = ast.parse(expr, mode='eval')
        expr = mod.body
        
    if expr.__class__ is ast.BoolOp:
        if all(is_boolean_expression(node, variables)
               for node in expr.values):
            return True
        else:
            raise SyntaxError("Expression ought to be boolean but is not (e.g. 'x<y and 3')")
    elif expr.__class__ is getattr(ast, 'NameConstant', None):
        value = expr.value
        if value is True or value is False:
            return True
        else:
            raise ValueError('Do not know how to deal with value %s' % value)
    elif expr.__class__ is ast.Name:
        name = expr.id
        if name in variables:
            return variables[name].is_boolean
        else:
            return name == 'True' or name == 'False'
    elif expr.__class__ is ast.Call:
        name = expr.func.id
        if name in variables and hasattr(variables[name], '_returns_bool'):
            return variables[name]._returns_bool
        else:
            raise SyntaxError('Unknown function %s' % name)
    elif expr.__class__ is ast.Compare:
        return True
    elif expr.__class__ is ast.UnaryOp:
        return expr.op.__class__.__name__ == 'Not'
    else:
        return False


def _get_value_from_expression(expr, variables):
    '''
    Returns the scalar value of an expression, and checks its validity.

    Parameters
    ----------
    expr : str or `ast.Expression`
        The expression to check.
    variables : dict of `Variable` objects
        The information about all variables used in `expr` (including `Constant`
        objects for external variables)

    Returns
    -------
    value : float
        The value of the expression

    Raises
    ------
    SyntaxError
        If the expression cannot be evaluated to a scalar value
    DimensionMismatchError
        If any part of the expression is dimensionally inconsistent.
    '''
    # If we are working on a string, convert to the top level node
    if isinstance(expr, basestring):
        mod = ast.parse(expr, mode='eval')
        expr = mod.body

    if expr.__class__ is ast.Name:
        name = expr.id
        if name in variables:
            if not getattr(variables[name], 'constant', False):
                raise SyntaxError('Value %s is not constant' % name)
            if not getattr(variables[name], 'scalar', False):
                raise SyntaxError('Value %s is not scalar' % name)
            return variables[name].get_value()
        elif name in ['True', 'False']:
            return 1.0 if name == 'True' else 0.0
        else:
            raise ValueError('Unknown identifier %s' % name)
    elif expr.__class__ is getattr(ast, 'NameConstant', None):
        value = expr.value
        if value is True or value is False:
            return 1.0 if value else 0.0
        else:
            raise ValueError('Do not know how to deal with value %s' % value)
    elif expr.__class__ is ast.Num:
        return expr.n
    elif expr.__class__ is ast.BoolOp:
        raise SyntaxError('Cannot determine the numerical value for a boolean operation.')
    elif expr.__class__ is ast.Compare:
        raise SyntaxError('Cannot determine the numerical value for a boolean operation.')
    elif expr.__class__ is ast.Call:
        raise SyntaxError('Cannot determine the numerical value for a function call.')
    elif expr.__class__ is ast.BinOp:
        op = expr.op.__class__.__name__
        left = _get_value_from_expression(expr.left, variables)
        right = _get_value_from_expression(expr.right, variables)
        if op=='Add' or op=='Sub':
            v = left + right
        elif op=='Mult':
            v = left * right
        elif op=='Div':
            v = left / right
        elif op=='Pow':
            v = left**right
        elif op=='Mod':
            v = left % right
        else:
            raise SyntaxError("Unsupported operation "+op)
        return v
    elif expr.__class__ is ast.UnaryOp:
        op = expr.op.__class__.__name__
        # check validity of operand and get its unit
        v =  _get_value_from_expression(expr.operand, variables)
        if op=='Not':
            raise SyntaxError(('Cannot determine the numerical value '
                               'for a boolean operation.'))
        if op=='USub':
            return -v
        else:
            raise SyntaxError('Unknown unary operation ' + op)
    else:
        raise SyntaxError('Unsupported operation ' + str(expr.__class__))

    
def parse_expression_dimensions(expr, variables):
    '''
    Returns the unit value of an expression, and checks its validity
    
    Parameters
    ----------
    expr : str
        The expression to check.
    variables : dict
        Dictionary of all variables used in the `expr` (including `Constant`
        objects for external variables)
    
    Returns
    -------
    unit : Quantity
        The output unit of the expression
    
    Raises
    ------
    SyntaxError
        If the expression cannot be parsed, or if it uses ``a**b`` for ``b``
        anything other than a constant number.
    DimensionMismatchError
        If any part of the expression is dimensionally inconsistent.
    '''

    # If we are working on a string, convert to the top level node    
    if isinstance(expr, basestring):
        mod = ast.parse(expr, mode='eval')
        expr = mod.body
    if expr.__class__ is getattr(ast, 'NameConstant', None):
        # new class for True, False, None in Python 3.4
        value = expr.value
        if value is True or value is False:
            return DIMENSIONLESS
        else:
            raise ValueError('Do not know how to handle value %s' % value)
    if expr.__class__ is ast.Name:
        name = expr.id
        # Raise an error if a function is called as if it were a variable
        # (most of the time this happens for a TimedArray)
        if name in variables and isinstance(variables[name], Function):
            raise SyntaxError('%s was used like a variable/constant, but it is '
                              'a function.' % name)
        if name in variables:
            return variables[name].dimensions
        elif name in ['True', 'False']:
            return DIMENSIONLESS
        else:
            raise KeyError('Unknown identifier %s' % name)
    elif expr.__class__ is ast.Num:
        return DIMENSIONLESS
    elif expr.__class__ is ast.BoolOp:
        # check that the units are valid in each subexpression
        for node in expr.values:
            parse_expression_dimensions(node, variables)
        # but the result is a bool, so we just return 1 as the unit
        return DIMENSIONLESS
    elif expr.__class__ is ast.Compare:
        # check that the units are consistent in each subexpression
        subexprs = [expr.left]+expr.comparators
        subunits = []
        for node in subexprs:
            subunits.append(parse_expression_dimensions(node, variables))
        for left, right in zip(subunits[:-1], subunits[1:]):
            if not have_same_dimensions(left, right):
                msg = ('Comparison of expressions with different units. Expression '
                       '"{}" has unit ({}), while expression "{}" has units ({})').format(
                            NodeRenderer().render_node(expr.left), get_dimensions(left),
                            NodeRenderer().render_node(expr.comparators[0]), get_dimensions(right))
                raise DimensionMismatchError(msg)
        # but the result is a bool, so we just return 1 as the unit
        return DIMENSIONLESS
    elif expr.__class__ is ast.Call:
        if len(expr.keywords):
            raise ValueError("Keyword arguments not supported.")
        elif getattr(expr, 'starargs', None) is not None:
            raise ValueError("Variable number of arguments not supported")
        elif getattr(expr, 'kwargs', None) is not None:
            raise ValueError("Keyword arguments not supported")

        func = variables.get(expr.func.id, None)
        if func is None:
            raise SyntaxError('Unknown function %s' % expr.func.id)
        if not hasattr(func, '_arg_units') or not hasattr(func, '_return_unit'):
            raise ValueError(('Function %s does not specify how it '
                              'deals with units.') % expr.func.id)

        if len(func._arg_units) != len(expr.args):
            raise SyntaxError('Function %s was called with %d parameters, '
                              'needs %d.' % (expr.func.id,
                                             len(expr.args),
                                             len(func._arg_units)))

        for idx, (arg, expected_unit) in enumerate(zip(expr.args,
                                                       func._arg_units)):
            # A "None" in func._arg_units means: No matter what unit
            if expected_unit is None:
                continue
            elif expected_unit == bool:
                if not is_boolean_expression(arg, variables):
                    raise TypeError(('Argument number %d for function %s was '
                                     'expected to be a boolean value, but is '
                                     '"%s".') % (idx + 1, expr.func.id,
                                                 NodeRenderer().render_node(arg)))
            else:
                arg_unit = parse_expression_dimensions(arg, variables)
                if not have_same_dimensions(arg_unit, expected_unit):
                    msg = ('Argument number {} for function {} does not have the '
                           'correct units. Expression "{}" has units ({}), but '
                           'should be ({}).').format(
                        idx+1, expr.func.id,
                        NodeRenderer().render_node(arg),
                        get_dimensions(arg_unit), get_dimensions(expected_unit))
                    raise DimensionMismatchError(msg)

        if func._return_unit == bool:
            return DIMENSIONLESS
        elif isinstance(func._return_unit, (Unit, int)):
            # Function always returns the same unit
            return getattr(func._return_unit, 'dim', DIMENSIONLESS)
        else:
            # Function returns a unit that depends on the arguments
            arg_units = [parse_expression_dimensions(arg, variables)
                         for arg in expr.args]
            return func._return_unit(*arg_units).dim

    elif expr.__class__ is ast.BinOp:
        op = expr.op.__class__.__name__
        left = parse_expression_dimensions(expr.left, variables)
        right = parse_expression_dimensions(expr.right, variables)
        if op=='Add' or op=='Sub' or op=='Mod':
            # dimensions should be the same
            op_symbol = {'Add': '+', 'Sub': '-', 'Mod': '%'}.get(op)
            fail_for_dimension_mismatch(left, right,
                                        'Cannot determine units for '
                                        '%s %s %s' % (NodeRenderer().render_node(expr.left),
                                                      op_symbol,
                                                      NodeRenderer().render_node(expr.right)))
            u = left
        elif op=='Mult':
            u = left*right
        elif op=='Div':
            u = left/right
        elif op=='Pow':
            if have_same_dimensions(left, 1) and have_same_dimensions(right, 1):
                return DIMENSIONLESS
            n = _get_value_from_expression(expr.right, variables)
            u = left**n
        else:
            raise SyntaxError("Unsupported operation "+op)
        return u
    elif expr.__class__ is ast.UnaryOp:
        op = expr.op.__class__.__name__
        # check validity of operand and get its unit
        u = parse_expression_dimensions(expr.operand, variables)
        if op=='Not':
            return DIMENSIONLESS
        else:
            return u
    else:
        raise SyntaxError('Unsupported operation ' + str(expr.__class__))

