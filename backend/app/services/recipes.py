from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem, FoodServing
from app.models.recipe import Recipe, RecipeIngredient, RecipeReport
from app.models.user import User
from app.schemas.recipes import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeRead,
    RecipeReportCreate,
    RecipeUpdate,
)
from app.services.foods import get_accessible_food_by_id, seed_verified_foods

NUTRIENT_QUANT = Decimal("0.01")
HUNDRED_GRAMS = Decimal("100")
DEMO_RECIPES_SYSTEM_EMAIL = "demo-recipes@nutrition-planner.local"
DEMO_RECIPES_SYSTEM_USERNAME = "demo_recipes"
DEMO_RECIPES_SYSTEM_DISPLAY_NAME = "Demo Recipes"
DEMO_RECIPES_SYSTEM_HASH = "seed_demo_recipes_user_hash"
DEMO_MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")

DEMO_BREAKFAST_RECIPES = [
    {
        "name": "Овсянка с бананом",
        "description": "Овсяные хлопья на молоке с бананом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Овсяные хлопья", "60"),
            ("Молоко 2.5%", "200"),
            ("Банан", "100"),
        ],
    },
    {
        "name": "Овсянка с яблоком и йогуртом",
        "description": "Овсяные хлопья с яблоком и греческим йогуртом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Овсяные хлопья", "55"),
            ("Йогурт греческий", "170"),
            ("Яблоко", "120"),
        ],
    },
    {
        "name": "Рисовая каша с бананом",
        "description": "Отварной рис с молоком и бананом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Рис отварной", "190"),
            ("Молоко 2.5%", "150"),
            ("Банан", "90"),
        ],
    },
    {
        "name": "Гречка с яйцом и огурцом",
        "description": "Гречка с варёным яйцом и свежим огурцом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Гречка отварная", "170"),
            ("Яйцо куриное", "100"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Омлет с сыром и томатом",
        "description": "Яичный омлет с сыром и помидорами",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Яйцо куриное", "120"),
            ("Сыр твердый", "20"),
            ("Помидор", "80"),
        ],
    },
    {
        "name": "Омлет с индейкой и томатом",
        "description": "Омлет с филе индейки и томатами",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Яйцо куриное", "100"),
            ("Индейка филе", "80"),
            ("Помидор", "100"),
        ],
    },
    {
        "name": "Творог с яблоком",
        "description": "Творог с нарезанным яблоком",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Творог 5%", "180"),
            ("Яблоко", "120"),
        ],
    },
    {
        "name": "Творог с бананом и йогуртом",
        "description": "Творог, банан и ложка греческого йогурта",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Творог 5%", "150"),
            ("Банан", "100"),
            ("Йогурт греческий", "80"),
        ],
    },
    {
        "name": "Тост с яйцом и огурцом",
        "description": "Цельнозерновой тост с яйцом и огурцом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Хлеб цельнозерновой", "70"),
            ("Яйцо куриное", "70"),
            ("Огурец", "100"),
        ],
    },
    {
        "name": "Йогуртовый боул с овсянкой и грушей",
        "description": "Греческий йогурт с овсяными хлопьями и грушей",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Йогурт греческий", "200"),
            ("Овсяные хлопья", "35"),
            ("Груша", "120"),
        ],
    },
    {
        "name": "Овсянка с арахисовой пастой и бананом",
        "description": "Плотная овсянка на молоке с бананом и арахисовой пастой",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Овсяные хлопья", "70"),
            ("Молоко 2.5%", "220"),
            ("Банан", "120"),
            ("Арахисовая паста", "20"),
        ],
    },
    {
        "name": "Тосты с творогом и бананом",
        "description": "Цельнозерновые тосты с творогом и бананом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Хлеб цельнозерновой", "100"),
            ("Творог 5%", "150"),
            ("Банан", "100"),
        ],
    },
    {
        "name": "Овсянка с апельсином и грушей",
        "description": "Овсяные хлопья на молоке с апельсином и грушей",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Овсяные хлопья", "65"),
            ("Молоко 2.5%", "220"),
            ("Апельсин", "120"),
            ("Груша", "120"),
        ],
    },
    {
        "name": "Рис с йогуртом и бананом",
        "description": "Отварной рис с греческим йогуртом и бананом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Рис отварной", "210"),
            ("Йогурт греческий", "180"),
            ("Банан", "110"),
        ],
    },
    {
        "name": "Гречневый боул с бананом и йогуртом",
        "description": "Гречка с бананом и греческим йогуртом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Гречка отварная", "220"),
            ("Йогурт греческий", "180"),
            ("Банан", "100"),
        ],
    },
    {
        "name": "Булгур с яблоком и йогуртом",
        "description": "Булгур с яблоком и греческим йогуртом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Булгур отварной", "250"),
            ("Яблоко", "140"),
            ("Йогурт греческий", "170"),
        ],
    },
    {
        "name": "Лаваш с творогом и бананом",
        "description": "Тонкий лаваш с творогом и бананом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Лаваш тонкий", "100"),
            ("Творог 5%", "120"),
            ("Банан", "90"),
        ],
    },
    {
        "name": "Кускус с апельсином и йогуртом",
        "description": "Кускус с апельсином и греческим йогуртом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Кускус отварной", "230"),
            ("Апельсин", "140"),
            ("Йогурт греческий", "170"),
        ],
    },
    {
        "name": "Тосты с нутом и огурцом",
        "description": "Цельнозерновые тосты с нутом и огурцом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Хлеб цельнозерновой", "100"),
            ("Нут вареный", "120"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Картофель с яйцом и томатом",
        "description": "Отварной картофель с яйцом и томатами",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "ingredients": [
            ("Картофель отварной", "300"),
            ("Яйцо куриное", "100"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Скрембл с томатом и тостом",
        "description": "Яичный скрембл с томатом и цельнозерновым тостом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 10,
        "ingredients": [
            ("Яйцо куриное", "120"),
            ("Помидор", "120"),
            ("Хлеб цельнозерновой", "70"),
        ],
    },
    {
        "name": "Творожный боул с грушей",
        "description": "Творог с грушей и ложкой йогурта",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 7,
        "ingredients": [
            ("Творог 5%", "170"),
            ("Груша", "130"),
            ("Йогурт греческий", "70"),
        ],
    },
    {
        "name": "Йогурт с яблоком и арахисовой пастой",
        "description": "Греческий йогурт с яблоком и арахисовой пастой",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 6,
        "ingredients": [
            ("Йогурт греческий", "200"),
            ("Яблоко", "120"),
            ("Арахисовая паста", "15"),
        ],
    },
    {
        "name": "Тост с тунцом и огурцом",
        "description": "Цельнозерновой тост с тунцом и свежим огурцом",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 8,
        "ingredients": [
            ("Хлеб цельнозерновой", "80"),
            ("Тунец консервированный", "90"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Кефирный смузи с бананом и овсянкой",
        "description": "Кефир, банан и овсяные хлопья в блендере",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 5,
        "ingredients": [
            ("Кефир 1%", "260"),
            ("Банан", "100"),
            ("Овсяные хлопья", "25"),
        ],
    },
    {
        "name": "Омлет с брокколи и сыром",
        "description": "Омлет с брокколи и тёртым сыром",
        "servings_count": 1,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 12,
        "ingredients": [
            ("Яйцо куриное", "120"),
            ("Брокколи", "120"),
            ("Сыр твердый", "20"),
        ],
    },
]

DEMO_LUNCH_RECIPES = [
    {
        "name": "Курица с рисом",
        "description": "Куриная грудка с рисом и томатом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Куриная грудка", "170"),
            ("Рис отварной", "180"),
            ("Помидор", "100"),
        ],
    },
    {
        "name": "Курица с пастой и томатом",
        "description": "Куриная грудка с макаронами и томатами",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Макароны отварные", "190"),
            ("Помидор", "130"),
        ],
    },
    {
        "name": "Индейка с гречкой",
        "description": "Филе индейки с гречкой и брокколи",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Индейка филе", "170"),
            ("Гречка отварная", "180"),
            ("Брокколи", "120"),
        ],
    },
    {
        "name": "Индейка с макаронами",
        "description": "Филе индейки с макаронами и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Индейка филе", "160"),
            ("Макароны отварные", "180"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Тунец с пастой",
        "description": "Тунец с отварными макаронами и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Тунец консервированный", "140"),
            ("Макароны отварные", "180"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Тунец с картофелем",
        "description": "Тунец, картофель и томаты",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Тунец консервированный", "130"),
            ("Картофель отварной", "220"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Говядина с рисом и брокколи",
        "description": "Постная говядина с рисом и брокколи",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Говядина постная", "150"),
            ("Рис отварной", "180"),
            ("Брокколи", "130"),
        ],
    },
    {
        "name": "Курица с картофелем и морковью",
        "description": "Куриная грудка с картофелем и морковью",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Картофель отварной", "210"),
            ("Морковь", "100"),
        ],
    },
    {
        "name": "Лосось с рисом и огурцом",
        "description": "Лосось с рисом и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Лосось", "130"),
            ("Рис отварной", "180"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Говядина с гречкой и капустой",
        "description": "Говядина с гречкой и тушёной капустой",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Говядина постная", "150"),
            ("Гречка отварная", "180"),
            ("Капуста белокочанная", "150"),
        ],
    },
    {
        "name": "Фасоль с рисом и овощами",
        "description": "Красная фасоль с рисом, томатом и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Фасоль красная вареная", "170"),
            ("Рис отварной", "170"),
            ("Помидор", "120"),
            ("Огурец", "100"),
        ],
    },
    {
        "name": "Паста с говядиной и оливковым маслом",
        "description": "Макароны с говядиной, томатами и оливковым маслом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Макароны отварные", "230"),
            ("Говядина постная", "150"),
            ("Помидор", "120"),
            ("Оливковое масло", "10"),
        ],
    },
    {
        "name": "Рис с лососем и оливковым маслом",
        "description": "Рис с лососем, брокколи и оливковым маслом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Рис отварной", "230"),
            ("Лосось", "150"),
            ("Брокколи", "120"),
            ("Оливковое масло", "8"),
        ],
    },
    {
        "name": "Курица с рисом и фасолью",
        "description": "Куриная грудка с рисом, фасолью и томатом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Рис отварной", "220"),
            ("Фасоль красная вареная", "120"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Тунец с рисом и фасолью",
        "description": "Тунец с рисом, фасолью и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Тунец консервированный", "140"),
            ("Рис отварной", "230"),
            ("Фасоль красная вареная", "110"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Индейка с булгуром и фасолью",
        "description": "Филе индейки с булгуром, фасолью и томатом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Индейка филе", "170"),
            ("Булгур отварной", "300"),
            ("Фасоль красная вареная", "170"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Курица с кускусом и нутом",
        "description": "Куриная грудка с кускусом, нутом и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Куриная грудка", "180"),
            ("Кускус отварной", "280"),
            ("Нут вареный", "140"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Тунец с картофелем и чечевицей",
        "description": "Тунец с картофелем, чечевицей и томатом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Тунец консервированный", "160"),
            ("Картофель отварной", "320"),
            ("Чечевица вареная", "180"),
            ("Помидор", "130"),
        ],
    },
    {
        "name": "Говядина с булгуром и овощами",
        "description": "Постная говядина с булгуром, брокколи и морковью",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Говядина постная", "170"),
            ("Булгур отварной", "300"),
            ("Брокколи", "150"),
            ("Морковь", "100"),
        ],
    },
    {
        "name": "Курица с гречкой и нутом",
        "description": "Куриная грудка с гречкой, нутом и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Куриная грудка", "170"),
            ("Гречка отварная", "260"),
            ("Нут вареный", "130"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Лаваш ролл с индейкой и фасолью",
        "description": "Лаваш с индейкой, фасолью и свежими томатами",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "ingredients": [
            ("Лаваш тонкий", "130"),
            ("Индейка филе", "150"),
            ("Фасоль красная вареная", "160"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Тёплый боул с индейкой и огурцом",
        "description": "Индейка с рисом, огурцом и лёгкой овощной подачей",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 15,
        "ingredients": [
            ("Индейка филе", "150"),
            ("Рис отварной", "170"),
            ("Огурец", "130"),
            ("Помидор", "100"),
        ],
    },
    {
        "name": "Салат с тунцом и фасолью",
        "description": "Тунец с фасолью, томатами и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 12,
        "ingredients": [
            ("Тунец консервированный", "130"),
            ("Фасоль красная вареная", "140"),
            ("Помидор", "130"),
            ("Огурец", "130"),
            ("Оливковое масло", "8"),
        ],
    },
    {
        "name": "Гречка с яйцом и брокколи",
        "description": "Гречка с яйцом и брокколи как быстрый обед",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 14,
        "ingredients": [
            ("Гречка отварная", "220"),
            ("Яйцо куриное", "120"),
            ("Брокколи", "130"),
        ],
    },
    {
        "name": "Паста с тунцом и томатами",
        "description": "Макароны с тунцом и свежими томатами",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 18,
        "ingredients": [
            ("Макароны отварные", "200"),
            ("Тунец консервированный", "120"),
            ("Помидор", "140"),
        ],
    },
    {
        "name": "Курица с булгуром и огурцом",
        "description": "Куриная грудка с булгуром и огурцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 19,
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Булгур отварной", "220"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Картофельный салат с индейкой",
        "description": "Тёплый картофельный салат с индейкой и овощами",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 20,
        "ingredients": [
            ("Картофель отварной", "240"),
            ("Индейка филе", "130"),
            ("Огурец", "110"),
            ("Помидор", "110"),
            ("Оливковое масло", "7"),
        ],
    },
    {
        "name": "Нут с овощами и яйцом",
        "description": "Нут с томатами, огурцом и варёным яйцом",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 15,
        "ingredients": [
            ("Нут вареный", "170"),
            ("Яйцо куриное", "100"),
            ("Помидор", "130"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Лаваш с курицей и брокколи",
        "description": "Лаваш с курицей, брокколи и лёгкой заправкой",
        "servings_count": 1,
        "meal_types": ["lunch"],
        "cook_time_minutes": 17,
        "ingredients": [
            ("Лаваш тонкий", "110"),
            ("Куриная грудка", "140"),
            ("Брокколи", "120"),
            ("Йогурт греческий", "60"),
        ],
    },
]

DEMO_DINNER_RECIPES = [
    {
        "name": "Лосось с картофелем",
        "description": "Лосось, картофель и брокколи",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Лосось", "160"),
            ("Картофель отварной", "200"),
            ("Брокколи", "120"),
        ],
    },
    {
        "name": "Лосось с рисом и брокколи",
        "description": "Лосось с рисом и брокколи",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Лосось", "140"),
            ("Рис отварной", "170"),
            ("Брокколи", "140"),
        ],
    },
    {
        "name": "Говядина с капустой",
        "description": "Постная говядина с тушёной капустой",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Говядина постная", "170"),
            ("Капуста белокочанная", "170"),
            ("Морковь", "70"),
        ],
    },
    {
        "name": "Говядина с картофелем",
        "description": "Говядина с картофелем и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Говядина постная", "150"),
            ("Картофель отварной", "210"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Индейка с овощами",
        "description": "Филе индейки с томатом и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Индейка филе", "170"),
            ("Помидор", "120"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Индейка с рисом и томатом",
        "description": "Филе индейки с рисом и томатами",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Индейка филе", "150"),
            ("Рис отварной", "180"),
            ("Помидор", "130"),
        ],
    },
    {
        "name": "Курица с гречкой и брокколи",
        "description": "Куриная грудка с гречкой и брокколи",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Гречка отварная", "180"),
            ("Брокколи", "130"),
        ],
    },
    {
        "name": "Курица с рисом и капустой",
        "description": "Курица с рисом и тушёной капустой",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Рис отварной", "170"),
            ("Капуста белокочанная", "170"),
        ],
    },
    {
        "name": "Тунец с рисом и овощами",
        "description": "Тунец с рисом, огурцом и томатом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Тунец консервированный", "130"),
            ("Рис отварной", "180"),
            ("Огурец", "100"),
            ("Помидор", "100"),
        ],
    },
    {
        "name": "Индейка с пастой и брокколи",
        "description": "Индейка с макаронами и брокколи",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Индейка филе", "150"),
            ("Макароны отварные", "180"),
            ("Брокколи", "130"),
        ],
    },
    {
        "name": "Фасоль с индейкой и томатом",
        "description": "Фасоль, индейка и томаты",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Фасоль красная вареная", "160"),
            ("Индейка филе", "110"),
            ("Помидор", "130"),
        ],
    },
    {
        "name": "Курица с пастой и оливковым маслом",
        "description": "Курица с макаронами, брокколи и оливковым маслом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Куриная грудка", "160"),
            ("Макароны отварные", "220"),
            ("Брокколи", "120"),
            ("Оливковое масло", "10"),
        ],
    },
    {
        "name": "Говядина с рисом и подсолнечным маслом",
        "description": "Говядина с рисом, капустой и подсолнечным маслом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Говядина постная", "160"),
            ("Рис отварной", "220"),
            ("Капуста белокочанная", "150"),
            ("Подсолнечное масло", "8"),
        ],
    },
    {
        "name": "Индейка с рисом и фасолью",
        "description": "Филе индейки с рисом, фасолью и томатом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Индейка филе", "150"),
            ("Рис отварной", "230"),
            ("Фасоль красная вареная", "120"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Курица с картофелем и фасолью",
        "description": "Куриная грудка с картофелем, фасолью и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Картофель отварной", "260"),
            ("Фасоль красная вареная", "110"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Индейка с кускусом и брокколи",
        "description": "Филе индейки с кускусом, брокколи и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Индейка филе", "160"),
            ("Кускус отварной", "250"),
            ("Брокколи", "170"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Курица с булгуром и овощами",
        "description": "Куриная грудка с булгуром, капустой и морковью",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Куриная грудка", "160"),
            ("Булгур отварной", "280"),
            ("Капуста белокочанная", "180"),
            ("Морковь", "120"),
        ],
    },
    {
        "name": "Тунец с булгуром и томатом",
        "description": "Тунец с булгуром, томатами и нутом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Тунец консервированный", "150"),
            ("Булгур отварной", "300"),
            ("Помидор", "180"),
            ("Нут вареный", "100"),
        ],
    },
    {
        "name": "Чечевица с курицей и картофелем",
        "description": "Чечевица, куриная грудка и картофель",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Чечевица вареная", "200"),
            ("Куриная грудка", "140"),
            ("Картофель отварной", "260"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Нут с индейкой и капустой",
        "description": "Нут с индейкой, капустой и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Нут вареный", "180"),
            ("Индейка филе", "140"),
            ("Капуста белокочанная", "200"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Лаваш с курицей и фасолью",
        "description": "Лаваш с курицей, фасолью и томатами",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "ingredients": [
            ("Лаваш тонкий", "120"),
            ("Куриная грудка", "140"),
            ("Фасоль красная вареная", "130"),
            ("Помидор", "120"),
        ],
    },
    {
        "name": "Индейка с томатами и кускусом",
        "description": "Быстрый ужин: индейка с кускусом и томатами",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 18,
        "ingredients": [
            ("Индейка филе", "150"),
            ("Кускус отварной", "210"),
            ("Помидор", "140"),
        ],
    },
    {
        "name": "Тунец с гречкой и огурцом",
        "description": "Тунец с гречкой и свежим огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 14,
        "ingredients": [
            ("Тунец консервированный", "130"),
            ("Гречка отварная", "200"),
            ("Огурец", "140"),
        ],
    },
    {
        "name": "Курица с брокколи и рисом",
        "description": "Куриная грудка с рисом и брокколи",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 19,
        "ingredients": [
            ("Куриная грудка", "150"),
            ("Рис отварной", "180"),
            ("Брокколи", "140"),
        ],
    },
    {
        "name": "Фасоль с яйцом и томатами",
        "description": "Фасоль с яйцом и томатами как быстрый ужин",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 12,
        "ingredients": [
            ("Фасоль красная вареная", "170"),
            ("Яйцо куриное", "110"),
            ("Помидор", "130"),
        ],
    },
    {
        "name": "Лосось с кускусом и огурцом",
        "description": "Лосось с кускусом и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 20,
        "ingredients": [
            ("Лосось", "130"),
            ("Кускус отварной", "200"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Говядина с кускусом и томатом",
        "description": "Постная говядина с кускусом и томатами",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 20,
        "ingredients": [
            ("Говядина постная", "140"),
            ("Кускус отварной", "220"),
            ("Помидор", "130"),
        ],
    },
    {
        "name": "Нут с индейкой и огурцом",
        "description": "Нут с индейкой и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 16,
        "ingredients": [
            ("Нут вареный", "160"),
            ("Индейка филе", "130"),
            ("Огурец", "130"),
        ],
    },
    {
        "name": "Лаваш с тунцом и овощами",
        "description": "Лаваш с тунцом, томатами и огурцом",
        "servings_count": 1,
        "meal_types": ["dinner"],
        "cook_time_minutes": 15,
        "ingredients": [
            ("Лаваш тонкий", "110"),
            ("Тунец консервированный", "120"),
            ("Помидор", "120"),
            ("Огурец", "120"),
        ],
    },
]

DEMO_SNACK_RECIPES = [
    {
        "name": "Йогурт с бананом",
        "description": "Греческий йогурт с бананом",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Йогурт греческий", "180"),
            ("Банан", "100"),
        ],
    },
    {
        "name": "Йогурт с яблоком и овсянкой",
        "description": "Греческий йогурт, яблоко и немного овсянки",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Йогурт греческий", "170"),
            ("Яблоко", "120"),
            ("Овсяные хлопья", "20"),
        ],
    },
    {
        "name": "Кефир с апельсином",
        "description": "Стакан кефира и апельсин",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Кефир 1%", "250"),
            ("Апельсин", "140"),
        ],
    },
    {
        "name": "Кефир с бананом и овсянкой",
        "description": "Кефир с бананом и небольшим количеством овсянки",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Кефир 1%", "250"),
            ("Банан", "90"),
            ("Овсяные хлопья", "20"),
        ],
    },
    {
        "name": "Тост с арахисовой пастой",
        "description": "Цельнозерновой тост с арахисовой пастой",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Хлеб цельнозерновой", "70"),
            ("Арахисовая паста", "30"),
        ],
    },
    {
        "name": "Банан с арахисовой пастой",
        "description": "Банан с арахисовой пастой как быстрый перекус",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Банан", "130"),
            ("Арахисовая паста", "20"),
        ],
    },
    {
        "name": "Творог с грушей",
        "description": "Творог 5% с грушей",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Творог 5%", "140"),
            ("Груша", "130"),
        ],
    },
    {
        "name": "Йогурт с апельсином и грушей",
        "description": "Греческий йогурт с апельсином и грушей",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Йогурт греческий", "170"),
            ("Апельсин", "100"),
            ("Груша", "100"),
        ],
    },
    {
        "name": "Йогурт с бананом и арахисовой пастой",
        "description": "Греческий йогурт с бананом и арахисовой пастой",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Йогурт греческий", "200"),
            ("Банан", "130"),
            ("Арахисовая паста", "20"),
        ],
    },
    {
        "name": "Тосты с арахисовой пастой и грушей",
        "description": "Цельнозерновые тосты с арахисовой пастой и грушей",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Хлеб цельнозерновой", "100"),
            ("Арахисовая паста", "25"),
            ("Груша", "120"),
        ],
    },
    {
        "name": "Кефир с яблоком и грушей",
        "description": "Кефир с яблоком и грушей",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Кефир 1%", "250"),
            ("Яблоко", "120"),
            ("Груша", "110"),
        ],
    },
    {
        "name": "Рисовый перекус с йогуртом и бананом",
        "description": "Отварной рис с греческим йогуртом и бананом",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Рис отварной", "150"),
            ("Йогурт греческий", "120"),
            ("Банан", "90"),
        ],
    },
    {
        "name": "Тост с йогуртом и яблоком",
        "description": "Цельнозерновой тост, йогурт и яблоко",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Хлеб цельнозерновой", "60"),
            ("Йогурт греческий", "130"),
            ("Яблоко", "120"),
        ],
    },
    {
        "name": "Кефир с бананом и грушей",
        "description": "Кефир с бананом и грушей",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Кефир 1%", "250"),
            ("Банан", "90"),
            ("Груша", "120"),
        ],
    },
    {
        "name": "Йогурт с кускусом и апельсином",
        "description": "Греческий йогурт с кускусом и апельсином",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Йогурт греческий", "150"),
            ("Кускус отварной", "120"),
            ("Апельсин", "120"),
        ],
    },
    {
        "name": "Лаваш с йогуртом и бананом",
        "description": "Лаваш с греческим йогуртом и бананом",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Лаваш тонкий", "60"),
            ("Йогурт греческий", "120"),
            ("Банан", "70"),
        ],
    },
    {
        "name": "Нутовый перекус с томатом и огурцом",
        "description": "Нут с томатом и огурцом",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Нут вареный", "120"),
            ("Помидор", "120"),
            ("Огурец", "120"),
        ],
    },
    {
        "name": "Тост с йогуртом и грушей",
        "description": "Цельнозерновой тост с йогуртом и грушей",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Хлеб цельнозерновой", "70"),
            ("Йогурт греческий", "120"),
            ("Груша", "110"),
        ],
    },
    {
        "name": "Булгур с кефиром и яблоком",
        "description": "Булгур, кефир и яблоко",
        "servings_count": 1,
        "meal_types": ["snack"],
        "ingredients": [
            ("Булгур отварной", "140"),
            ("Кефир 1%", "220"),
            ("Яблоко", "120"),
        ],
    },
    {
        "name": "Творог с апельсином",
        "description": "Творог 5% с дольками апельсина",
        "servings_count": 1,
        "meal_types": ["snack"],
        "cook_time_minutes": 5,
        "ingredients": [
            ("Творог 5%", "150"),
            ("Апельсин", "140"),
        ],
    },
    {
        "name": "Кефир с бананом и арахисовой пастой",
        "description": "Кефир, банан и немного арахисовой пасты",
        "servings_count": 1,
        "meal_types": ["snack"],
        "cook_time_minutes": 8,
        "ingredients": [
            ("Кефир 1%", "250"),
            ("Банан", "90"),
            ("Арахисовая паста", "12"),
        ],
    },
    {
        "name": "Тост с творогом и огурцом",
        "description": "Цельнозерновой тост с творогом и огурцом",
        "servings_count": 1,
        "meal_types": ["snack"],
        "cook_time_minutes": 7,
        "ingredients": [
            ("Хлеб цельнозерновой", "70"),
            ("Творог 5%", "90"),
            ("Огурец", "110"),
        ],
    },
    {
        "name": "Яйцо с огурцом и томатом",
        "description": "Варёное яйцо с огурцом и томатом",
        "servings_count": 1,
        "meal_types": ["snack"],
        "cook_time_minutes": 10,
        "ingredients": [
            ("Яйцо куриное", "100"),
            ("Огурец", "100"),
            ("Помидор", "100"),
        ],
    },
]

DEMO_PUBLIC_RECIPES = [
    *DEMO_BREAKFAST_RECIPES,
    *DEMO_LUNCH_RECIPES,
    *DEMO_DINNER_RECIPES,
    *DEMO_SNACK_RECIPES,
]
DEMO_COOK_TIME_RANGES_BY_MEAL_TYPE: dict[str, tuple[int, int]] = {
    "breakfast": (5, 20),
    "snack": (5, 20),
    "lunch": (20, 60),
    "dinner": (20, 60),
}


class RecipeNotFoundError(ValueError):
    pass


class RecipeIngredientNotFoundError(ValueError):
    pass


class RecipeIngredientFoodNotFoundError(ValueError):
    pass


class RecipeIngredientServingMismatchError(ValueError):
    pass


class RecipePublishConflictError(ValueError):
    pass


class RecipeNotEditableError(ValueError):
    pass


class RecipeReportConflictError(ValueError):
    pass


class RecipeReportNotAllowedError(ValueError):
    pass


def _assign_demo_cook_time_minutes() -> None:
    for recipe_index, payload in enumerate(DEMO_PUBLIC_RECIPES):
        if payload.get("cook_time_minutes") is not None:
            continue

        meal_types = payload.get("meal_types") or []
        primary_meal_type = meal_types[0] if meal_types else "lunch"
        lower, upper = DEMO_COOK_TIME_RANGES_BY_MEAL_TYPE.get(primary_meal_type, (20, 60))
        span = max(1, upper - lower + 1)
        payload["cook_time_minutes"] = lower + (recipe_index % span)


_assign_demo_cook_time_minutes()


class RecipeReportSelfError(ValueError):
    pass


class RecipeWithdrawForbiddenError(ValueError):
    pass


class RecipeWithdrawConflictError(ValueError):
    pass


def _quantize_nutrient(value: Decimal) -> Decimal:
    return value.quantize(NUTRIENT_QUANT, rounding=ROUND_HALF_UP)


def _resolve_ingredient_measurement(
    db: Session,
    *,
    food_id: int,
    grams: Decimal | None,
    serving_id: int | None,
    multiplier: Decimal | None,
) -> tuple[Decimal, int | None, Decimal | None]:
    if grams is not None:
        return grams, None, None

    if serving_id is None or multiplier is None:
        raise RecipeIngredientServingMismatchError("Provide grams or serving with multiplier")

    serving = db.execute(
        select(FoodServing).where(FoodServing.id == serving_id)
    ).scalar_one_or_none()
    if not serving or serving.food_id != food_id:
        raise RecipeIngredientServingMismatchError("Serving does not match selected food")

    resolved_grams = _quantize_nutrient(serving.grams * multiplier)
    return resolved_grams, serving.id, multiplier


def ensure_recipe_editable(recipe: Recipe) -> None:
    if recipe.source != FoodSource.private or recipe.status != FoodStatus.draft:
        raise RecipeNotEditableError("Only private draft recipes can be modified")


def create_recipe(db: Session, owner_id: int, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        owner_user_id=owner_id,
        name=data.name,
        description=data.description,
        servings_count=data.servings_count,
        meal_types=data.meal_types,
        cook_time_minutes=data.cook_time_minutes,
        source=FoodSource.private,
        status=FoodStatus.draft,
        is_listed=True,
        reports_count=0,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def build_accessible_recipes_condition(
    *,
    user_id: int,
    include_public: bool,
):
    if not include_public:
        return Recipe.owner_user_id == user_id

    return or_(
        Recipe.owner_user_id == user_id,
        and_(
            Recipe.source == FoodSource.community,
            Recipe.status == FoodStatus.approved,
            Recipe.is_listed.is_(True),
        ),
    )


def list_my_recipes(
    db: Session,
    owner_id: int,
    limit: int = 50,
    offset: int = 0,
    *,
    include_ingredients: bool = False,
) -> list[Recipe]:
    query = (
        select(Recipe)
        .where(Recipe.owner_user_id == owner_id)
        .order_by(Recipe.updated_at.desc(), Recipe.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if include_ingredients:
        query = query.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    return db.execute(query).scalars().all()


def list_accessible_recipes(
    db: Session,
    user_id: int,
    *,
    include_public: bool,
    limit: int = 50,
    offset: int = 0,
    include_ingredients: bool = False,
) -> list[Recipe]:
    stmt = (
        select(Recipe)
        .where(
            build_accessible_recipes_condition(
                user_id=user_id,
                include_public=include_public,
            )
        )
        .order_by(Recipe.updated_at.desc(), Recipe.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if include_ingredients:
        stmt = stmt.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    return db.execute(stmt).scalars().all()


def get_my_recipe_or_404(
    db: Session,
    owner_id: int,
    recipe_id: int,
    *,
    include_ingredients: bool = False,
) -> Recipe:
    stmt = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.owner_user_id == owner_id,
    )
    if include_ingredients:
        stmt = stmt.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    result = db.execute(stmt)
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise RecipeNotFoundError("Recipe not found")
    return recipe


def get_owned_recipe_or_none(
    db: Session,
    owner_id: int,
    recipe_id: int,
    *,
    include_ingredients: bool = False,
) -> Recipe | None:
    stmt = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.owner_user_id == owner_id,
    )
    if include_ingredients:
        stmt = stmt.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def get_accessible_recipe_by_id(
    db: Session,
    user_id: int,
    recipe_id: int,
    *,
    include_ingredients: bool = False,
) -> Recipe | None:
    stmt = select(Recipe).where(Recipe.id == recipe_id)
    if include_ingredients:
        stmt = stmt.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )

    stmt = stmt.where(
        build_accessible_recipes_condition(
            user_id=user_id,
            include_public=True,
        )
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def update_my_recipe(db: Session, owner_id: int, recipe_id: int, data: RecipeUpdate) -> Recipe:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recipe, field, value)

    db.commit()
    db.refresh(recipe)
    return recipe


def delete_my_recipe(db: Session, owner_id: int, recipe_id: int) -> None:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    db.delete(recipe)
    db.commit()


def _get_recipe_ingredient_or_404(db: Session, recipe_id: int, ingredient_id: int) -> RecipeIngredient:
    ingredient = db.execute(
        select(RecipeIngredient).where(
            RecipeIngredient.id == ingredient_id,
            RecipeIngredient.recipe_id == recipe_id,
        )
    ).scalar_one_or_none()
    if not ingredient:
        raise RecipeIngredientNotFoundError("Ingredient not found")
    return ingredient


def add_ingredient(
    db: Session,
    owner_id: int,
    recipe_id: int,
    data: RecipeIngredientCreate,
) -> RecipeIngredient:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    food = get_accessible_food_by_id(db, owner_id, data.food_id)
    if not food:
        raise RecipeIngredientFoodNotFoundError("Food not found")

    grams, serving_id, multiplier = _resolve_ingredient_measurement(
        db,
        food_id=data.food_id,
        grams=data.grams,
        serving_id=data.serving_id,
        multiplier=data.multiplier,
    )

    ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        food_id=data.food_id,
        grams=grams,
        serving_id=serving_id,
        multiplier=multiplier,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def update_ingredient(
    db: Session,
    owner_id: int,
    recipe_id: int,
    ingredient_id: int,
    data: RecipeIngredientUpdate,
) -> RecipeIngredient:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    ingredient = _get_recipe_ingredient_or_404(db, recipe.id, ingredient_id)

    update_data = data.model_dump(exclude_unset=True)
    next_food_id = update_data.get("food_id", ingredient.food_id)
    if "food_id" in update_data:
        food = get_accessible_food_by_id(db, owner_id, next_food_id)
        if not food:
            raise RecipeIngredientFoodNotFoundError("Food not found")

    next_grams = ingredient.grams
    next_serving_id = ingredient.serving_id
    next_multiplier = ingredient.multiplier

    has_explicit_grams = "grams" in update_data and update_data["grams"] is not None
    has_serving_payload = "serving_id" in update_data or "multiplier" in update_data

    if has_explicit_grams:
        next_grams = update_data["grams"]
        next_serving_id = None
        next_multiplier = None
    elif has_serving_payload:
        if "serving_id" in update_data:
            next_serving_id = update_data["serving_id"]
        if "multiplier" in update_data:
            next_multiplier = update_data["multiplier"]

        if next_serving_id is None:
            if "serving_id" in update_data and update_data["serving_id"] is None:
                next_serving_id = None
                next_multiplier = None
            elif "multiplier" in update_data:
                raise RecipeIngredientServingMismatchError("Serving must be selected for multiplier mode")
        else:
            next_grams, next_serving_id, next_multiplier = _resolve_ingredient_measurement(
                db,
                food_id=next_food_id,
                grams=None,
                serving_id=next_serving_id,
                multiplier=next_multiplier,
            )
    elif "food_id" in update_data and next_serving_id is not None:
        next_grams, next_serving_id, next_multiplier = _resolve_ingredient_measurement(
            db,
            food_id=next_food_id,
            grams=None,
            serving_id=next_serving_id,
            multiplier=next_multiplier,
        )

    ingredient.food_id = next_food_id
    ingredient.grams = next_grams
    ingredient.serving_id = next_serving_id
    ingredient.multiplier = next_multiplier

    db.commit()
    db.refresh(ingredient)
    return ingredient


def delete_ingredient(db: Session, owner_id: int, recipe_id: int, ingredient_id: int) -> None:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    ingredient = _get_recipe_ingredient_or_404(db, recipe.id, ingredient_id)
    db.delete(ingredient)
    db.commit()


def publish_recipe(db: Session, owner_id: int, recipe_id: int) -> Recipe | None:
    recipe = get_owned_recipe_or_none(db, owner_id, recipe_id)
    if not recipe:
        return None

    if recipe.source != FoodSource.private or recipe.status != FoodStatus.draft:
        raise RecipePublishConflictError("Recipe is already published or cannot be published")

    recipe.source = FoodSource.community
    recipe.status = FoodStatus.approved
    recipe.is_listed = True
    db.commit()
    db.refresh(recipe)
    return recipe


def withdraw_recipe(db: Session, owner_id: int, recipe_id: int) -> Recipe | None:
    recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
    if not recipe:
        return None

    if recipe.owner_user_id != owner_id:
        raise RecipeWithdrawForbiddenError("Only owner can withdraw this recipe")

    if recipe.source != FoodSource.community or recipe.status != FoodStatus.approved:
        raise RecipeWithdrawConflictError("Only approved community recipes can be withdrawn")

    if not recipe.is_listed:
        raise RecipeWithdrawConflictError("Recipe is already withdrawn")

    recipe.is_listed = False
    db.commit()
    db.refresh(recipe)
    return recipe


def report_recipe(
    db: Session,
    reporter_user_id: int,
    recipe_id: int,
    payload: RecipeReportCreate,
) -> Recipe | None:
    recipe = db.execute(
        select(Recipe).where(Recipe.id == recipe_id).with_for_update()
    ).scalar_one_or_none()
    if not recipe:
        return None

    if recipe.owner_user_id == reporter_user_id:
        raise RecipeReportSelfError("You cannot report your own recipe")

    if (
        recipe.source != FoodSource.community
        or recipe.status != FoodStatus.approved
        or not recipe.is_listed
    ):
        return None

    db.add(
        RecipeReport(
            recipe_id=recipe_id,
            reporter_user_id=reporter_user_id,
            reason=payload.reason,
            comment=payload.comment,
        )
    )

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise RecipeReportConflictError("You have already reported this recipe") from exc

    reports_count = db.execute(
        select(func.count(RecipeReport.id)).where(RecipeReport.recipe_id == recipe_id)
    ).scalar_one()
    recipe.reports_count = int(reports_count or 0)

    if recipe.reports_count >= 3:
        recipe.status = FoodStatus.pending
        recipe.is_listed = False

    db.commit()
    db.refresh(recipe)
    return recipe


def _get_or_create_demo_recipes_user(db: Session) -> User:
    user = db.execute(
        select(User).where(
            or_(
                User.email == DEMO_RECIPES_SYSTEM_EMAIL,
                User.username == DEMO_RECIPES_SYSTEM_USERNAME,
            )
        )
    ).scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=DEMO_RECIPES_SYSTEM_EMAIL,
        username=DEMO_RECIPES_SYSTEM_USERNAME,
        display_name=DEMO_RECIPES_SYSTEM_DISPLAY_NAME,
        hashed_password=DEMO_RECIPES_SYSTEM_HASH,
    )
    db.add(user)
    db.flush()
    return user


def _get_verified_foods_by_name(db: Session, *, names: list[str]) -> dict[str, FoodItem]:
    foods = db.execute(
        select(FoodItem).where(
            FoodItem.source == FoodSource.verified,
            FoodItem.name.in_(names),
        )
    ).scalars().all()

    foods_by_name: dict[str, FoodItem] = {}
    for food in foods:
        foods_by_name.setdefault(food.name, food)
    return foods_by_name


def seed_demo_public_recipes(
    db: Session,
    *,
    replace_demo: bool = False,
) -> dict[str, int]:
    created_verified_foods = seed_verified_foods(db)
    demo_user = _get_or_create_demo_recipes_user(db)

    existing_demo_recipes: list[Recipe] = []
    if replace_demo:
        recipes_for_demo_user = db.execute(
            select(Recipe).where(Recipe.owner_user_id == demo_user.id)
        ).scalars().all()
        for recipe in recipes_for_demo_user:
            db.delete(recipe)
        db.flush()
    else:
        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        existing_demo_recipes = db.execute(
            select(Recipe).where(
                Recipe.owner_user_id == demo_user.id,
                Recipe.name.in_(demo_names),
            )
        ).scalars().all()

    existing_by_name = {recipe.name: recipe for recipe in existing_demo_recipes}

    required_food_names = sorted(
        {food_name for recipe in DEMO_PUBLIC_RECIPES for food_name, _grams in recipe["ingredients"]}
    )
    verified_foods_by_name = _get_verified_foods_by_name(db, names=required_food_names)
    missing_foods = [name for name in required_food_names if name not in verified_foods_by_name]
    if missing_foods:
        raise ValueError(f"Missing verified foods for demo recipes: {', '.join(missing_foods)}")

    created_recipes = 0
    skipped_recipes = 0
    for payload in DEMO_PUBLIC_RECIPES:
        if payload["name"] in existing_by_name:
            skipped_recipes += 1
            continue

        recipe = Recipe(
            owner_user_id=demo_user.id,
            name=payload["name"],
            description=payload["description"],
            servings_count=payload["servings_count"],
            meal_types=payload["meal_types"],
            cook_time_minutes=payload.get("cook_time_minutes"),
            source=FoodSource.community,
            status=FoodStatus.approved,
            is_listed=True,
            reports_count=0,
        )
        db.add(recipe)
        db.flush()

        for food_name, grams in payload["ingredients"]:
            db.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    food_id=verified_foods_by_name[food_name].id,
                    grams=Decimal(grams),
                    serving_id=None,
                    multiplier=None,
                )
            )

        created_recipes += 1

    db.commit()

    meal_type_distribution = {meal_type: 0 for meal_type in DEMO_MEAL_TYPES}
    for recipe in DEMO_PUBLIC_RECIPES:
        for meal_type in recipe["meal_types"]:
            meal_type_distribution[meal_type] += 1

    return {
        "created_recipes": created_recipes,
        "skipped_recipes": skipped_recipes,
        "total_demo_recipes": len(DEMO_PUBLIC_RECIPES),
        "created_verified_foods": int(created_verified_foods),
        **meal_type_distribution,
    }


def calculate_recipe_nutrients(recipe: Recipe) -> dict[str, Decimal]:
    total_grams = Decimal("0")
    total_kcal = Decimal("0")
    total_protein = Decimal("0")
    total_fat = Decimal("0")
    total_carbs = Decimal("0")

    for ingredient in recipe.ingredients:
        if ingredient.food is None:
            continue

        factor = ingredient.grams / HUNDRED_GRAMS
        total_grams += ingredient.grams
        total_kcal += ingredient.food.kcal * factor
        total_protein += ingredient.food.protein * factor
        total_fat += ingredient.food.fat * factor
        total_carbs += ingredient.food.carbs * factor

    servings_count = Decimal(recipe.servings_count)
    per_serving_kcal = total_kcal / servings_count
    per_serving_protein = total_protein / servings_count
    per_serving_fat = total_fat / servings_count
    per_serving_carbs = total_carbs / servings_count

    return {
        "total_grams": _quantize_nutrient(total_grams),
        "total_kcal": _quantize_nutrient(total_kcal),
        "total_protein": _quantize_nutrient(total_protein),
        "total_fat": _quantize_nutrient(total_fat),
        "total_carbs": _quantize_nutrient(total_carbs),
        "per_serving_kcal": _quantize_nutrient(per_serving_kcal),
        "per_serving_protein": _quantize_nutrient(per_serving_protein),
        "per_serving_fat": _quantize_nutrient(per_serving_fat),
        "per_serving_carbs": _quantize_nutrient(per_serving_carbs),
    }


def build_recipe_read(recipe: Recipe) -> RecipeRead:
    nutrients = calculate_recipe_nutrients(recipe)
    ingredients_payload = []
    for ingredient in recipe.ingredients:
        ingredients_payload.append(
            {
                "id": ingredient.id,
                "recipe_id": ingredient.recipe_id,
                "food_id": ingredient.food_id,
                "grams": ingredient.grams,
                "serving_id": ingredient.serving_id,
                "multiplier": ingredient.multiplier,
                "created_at": ingredient.created_at,
                "updated_at": ingredient.updated_at,
                "food": (
                    {
                        "id": ingredient.food.id,
                        "name": ingredient.food.name,
                        "brand": ingredient.food.brand,
                    }
                    if ingredient.food is not None
                    else None
                ),
            }
        )

    return RecipeRead.model_validate(
        {
            "id": recipe.id,
            "owner_user_id": recipe.owner_user_id,
            "name": recipe.name,
            "description": recipe.description,
            "servings_count": recipe.servings_count,
            "meal_types": recipe.meal_types,
            "cook_time_minutes": recipe.cook_time_minutes,
            "source": recipe.source,
            "status": recipe.status,
            "reports_count": recipe.reports_count,
            "is_listed": recipe.is_listed,
            "ingredients": ingredients_payload,
            "created_at": recipe.created_at,
            "updated_at": recipe.updated_at,
            **nutrients,
        }
    )
