from app.services.dish_image import pick_prompt_title

# Dữ liệu thật công thức 418 (Food.com, chưa verified).
DB_TITLE = "chicken hurry"
INGREDIENTS_VI = ["Hành tây", "Gà nguyên con", "Đường nâu", "Tương cà"]


def test_adapted_title_built_from_ingredients_and_cooking_words_is_used() -> None:
    assert pick_prompt_title("Gà nướng hành tây", DB_TITLE, INGREDIENTS_VI) == "Gà nướng hành tây"


def test_title_with_word_outside_recipe_falls_back_to_db_title() -> None:
    assert pick_prompt_title("Gà nướng hành tây ngon tuyệt", DB_TITLE, INGREDIENTS_VI) == DB_TITLE
    assert pick_prompt_title("Bò nướng hành tây", DB_TITLE, INGREDIENTS_VI) == DB_TITLE


def test_title_of_only_cooking_words_falls_back() -> None:
    assert pick_prompt_title("Nướng và xào", DB_TITLE, INGREDIENTS_VI) == DB_TITLE


def test_missing_title_uses_db_title() -> None:
    assert pick_prompt_title(None, DB_TITLE, INGREDIENTS_VI) == DB_TITLE
    assert pick_prompt_title("", DB_TITLE, INGREDIENTS_VI) == DB_TITLE


def test_punctuation_is_stripped_so_it_cannot_break_the_prompt() -> None:
    assert pick_prompt_title('Gà". nướng, hành tây!', DB_TITLE, INGREDIENTS_VI) == "Gà nướng hành tây"


def test_title_equal_to_db_title_is_used() -> None:
    assert pick_prompt_title("Trứng Gà Ngâm Mật Ong", "Trứng Gà Ngâm Mật Ong", ["Trứng gà", "Mật ong"]) == "Trứng Gà Ngâm Mật Ong"
