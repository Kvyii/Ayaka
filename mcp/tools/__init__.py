from tools.kanji import register_kanji_tools
from tools.vocab import register_vocab_tools
from tools.grammar import register_grammar_tools


def register_all_tools(mcp):
    register_kanji_tools(mcp)
    register_vocab_tools(mcp)
    register_grammar_tools(mcp)
