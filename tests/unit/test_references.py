from smartrecon.matching.references import compile_known_reference_patterns, extract_known_references


def test_precompiled_reference_patterns_keep_boundary_and_separator_semantics() -> None:
    known = {"ORD00003", "DH01", "DH010"}
    compiled = compile_known_reference_patterns(known)

    assert extract_known_references("thanh toan ord 00003", known, compiled_patterns=compiled) == ("ORD00003",)
    assert extract_known_references("thanh toan DH01", known, compiled_patterns=compiled) == ("DH01",)
    assert extract_known_references("prefixDH01suffix", known, compiled_patterns=compiled) == ()
    assert len(compiled) == len(known)
