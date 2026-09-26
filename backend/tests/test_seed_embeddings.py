from scripts.seed_embeddings import build_recipe_embed_text


def test_embed_text_merges_vi_en_and_raw_names_without_duplicates() -> None:
    recipe = {
        "title": "Gà xào sả ớt",
        "recipe_ingredients": [
            {"ingredients": {"name_vi": "Thịt gà", "name_en": "Chicken"}},
            {"ingredients": {"name_vi": "Sả", "name_en": None}},
            {"ingredients": {"name_vi": "Ớt", "name_en": "Ớt"}},
        ],
        "raw_ingredient_names": ["nước mắm ", "Chicken"],
    }
    assert build_recipe_embed_text(recipe) == "Gà xào sả ớt. Nguyên liệu: Thịt gà, Chicken, Sả, Ớt, nước mắm"
