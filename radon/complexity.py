'''This module contains all high-level helpers function that allow to work with
Cyclomatic Complexity
'''

import math
from flake8_polyfill import options
from radon.visitors import GET_COMPLEXITY, ComplexityVisitor, code2ast


# sorted_block ordering functions
SCORE = lambda block: -GET_COMPLEXITY(block)
LINES = lambda block: block.lineno
ALPHA = lambda block: block.name


def cc_rank(cc):
    r'''Rank the complexity score from A to F, where A stands for the simplest
    and best score and F the most complex and worst one:

    ============= =====================================================
        1 - 5        A (low risk - simple block)
        6 - 10       B (low risk - well structured and stable block)
        11 - 20      C (moderate risk - slightly complex block)
        21 - 30      D (more than moderate risk - more complex block)
        31 - 40      E (high risk - complex block, alarming)
        41+          F (very high risk - error-prone, unstable block)
    ============= =====================================================

    Here *block* is used in place of function, method or class.

    The formula used to convert the score into an index is the following:

    .. math::

        \text{rank} = \left \lceil \dfrac{\text{score}}{10} \right \rceil
        - H(5 - \text{score})

    where ``H(s)`` stands for the Heaviside Step Function.
    The rank is then associated to a letter (0 = A, 5 = F).
    '''
    if cc < 0:
        raise ValueError('Complexity must be a non-negative value')
    return chr(min(int(math.ceil(cc / 10.) or 1) - (1, 0)[5 - cc < 0], 5) + 65)


def average_complexity(blocks):
    '''Compute the average Cyclomatic complexity from the given blocks.
    Blocks must be either :class:`~radon.visitors.Function` or
    :class:`~radon.visitors.Class`. If the block list is empty, then 0 is
    returned.
    '''
    size = len(blocks)
    if size == 0:
        return 0
    return sum((GET_COMPLEXITY(block) for block in blocks), .0) / len(blocks)


def sorted_results(blocks, order=SCORE):
    '''Given a ComplexityVisitor instance, returns a list of sorted blocks
    with respect to complexity. A block is a either
    :class:`~radon.visitors.Function` object or a
    :class:`~radon.visitors.Class` object.
    The blocks are sorted in descending order from the block with the highest
    complexity.

    The optional `order` parameter indicates how to sort the blocks. It can be:

        * `LINES`: sort by line numbering;
        * `ALPHA`: sort by name (from A to Z);
        * `SCORE`: sorty by score (descending).

    Default is `SCORE`.
    '''
    return sorted(blocks, key=order)


def add_inner_blocks(blocks):
    '''Process a list of blocks by adding all closures and inner classes as
    top-level blocks.
    '''
    new_blocks = []
    all_blocks = blocks[:]
    while all_blocks:
        block = all_blocks.pop()
        new_blocks.append(block)
        for inner_block in ('closures', 'inner_classes'):
            for i_block in getattr(block, inner_block, ()):
                named = i_block._replace(name=block.name + '.' + i_block.name)
                all_blocks.append(named)
                for meth in getattr(named, 'methods', ()):
                    m_named = meth._replace(classname=named.name)
                    all_blocks.append(m_named)
    return new_blocks


def cc_visit(code, **kwargs):
    '''Visit the given code with :class:`~radon.visitors.ComplexityVisitor`.
    All the keyword arguments are directly passed to the visitor.
    '''
    return cc_visit_ast(code2ast(code), **kwargs)


def cc_visit_ast(ast_node, **kwargs):
    '''Visit the AST node with :class:`~radon.visitors.ComplexityVisitor`. All
    the keyword arguments are directly passed to the visitor.
    '''
    return ComplexityVisitor.from_ast(ast_node, **kwargs).blocks


class Flake8Checker(object):
    '''Entry point for the Flake8 tool.'''

    name = 'radon'
    _code = 'R701'
    _error_tmpl = 'R701: %r is too complex (%d)'
    no_assert = False
    max_cc = -1

    def __init__(self, tree, filename):
        '''Accept the AST tree and a filename (unused).'''
        self.tree = tree

    version = property(lambda self: __import__('radon').__version__)

    @classmethod
    def add_options(cls, parser):  # pragma: no cover
        '''Add custom options to the global parser.'''
        options.register(
            parser,
            '--radon-max-cc', default=-1, action='store',
            type='int', help='Radon complexity threshold',
            parse_from_config=True
        )
        options.register(
            parser,
            '--radon-no-assert', dest='no_assert', action='store_true',
            default=False, help='Radon will ignore assert statements',
            parse_from_config=True,
        )

    @classmethod
    def parse_options(cls, options):  # pragma: no cover
        '''Save actual options as class attributes.'''
        cls.max_cc = options.radon_max_cc
        cls.no_assert = options.no_assert

    def run(self):
        '''Run the ComplexityVisitor over the AST tree.'''
        if self.max_cc < 0:
            if not self.no_assert:
                return
            self.max_cc = 10
        visitor = ComplexityVisitor.from_ast(self.tree,
                                             no_assert=self.no_assert)
        for block in visitor.blocks:
            if block.complexity > self.max_cc:
                text = self._error_tmpl % (block.name, block.complexity)
                yield block.lineno, block.col_offset, text, type(self)
