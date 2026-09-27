"""Kiểu dùng chung cho chế độ ăn và dị ứng (gợi ý công thức + hồ sơ user)."""

from typing import Literal

DietType = Literal["omnivore", "vegetarian", "vegan"]
# Phải khớp bảng allergens (test đối chiếu DB): slug lạ bị từ chối thay vì âm thầm không lọc dị ứng.
AllergenSlug = Literal["shellfish", "molluscs", "fish", "egg", "dairy", "peanut", "tree_nuts", "soy", "wheat", "sesame"]
