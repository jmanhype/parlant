import enum
from typing import Literal
from supabase import create_client
import os

from parlant.core.tools import ToolResult

supabase_url = os.environ["SUPABASE_URL"]
supabase_anon = os.environ["SUPABASE_ANON_KEY"]
supabase = create_client(supabase_url, supabase_anon)


def get_available_drinks() -> ToolResult:
    return ToolResult(["Sprite", "Coca Cola"])


def get_available_toppings() -> ToolResult:
    return ToolResult(["Pepperoni", "Mushrooms", "Olives"])


def expert_answer(user_query: str) -> ToolResult:
    answers = {"Hey, where are your offices located?": "Our Offices located in Tel Aviv"}
    return ToolResult(answers[user_query])


def get_available_product_by_type(product_type: Literal["drinks", "toppings"]) -> ToolResult:
    if product_type == "drinks":
        return get_available_drinks()
    elif product_type == "toppings":
        return get_available_toppings()
    else:
        return ToolResult([])


def add(first_number: int, second_number: int) -> ToolResult:
    return ToolResult(first_number + second_number)


def multiply(first_number: int, second_number: int) -> ToolResult:
    return ToolResult(first_number * second_number)


def get_account_balance(account_name: str) -> ToolResult:
    balances = {
        "Jerry Seinfeld": 1000000000,
        "Larry David": 450000000,
        "John Smith": 100,
    }
    return ToolResult(balances.get(account_name, -555))


def get_account_loans(account_name: str) -> ToolResult:
    portfolios = {
        "Jerry Seinfeld": 100,
        "Larry David": 50,
    }
    return ToolResult(portfolios[account_name])


def transfer_money(from_account: str, to_account: str) -> ToolResult:
    return ToolResult(True)


def get_terrys_offering() -> ToolResult:
    return ToolResult("Terry offers leaf")


def schedule() -> ToolResult:
    return ToolResult("Meeting got scheduled!")


def check_fruit_price(fruit: str) -> ToolResult:
    return ToolResult(f"1 kg of {fruit} costs 10$")


def check_vegetable_price(vegetable: str) -> ToolResult:
    return ToolResult(f"1 kg of {vegetable} costs 3$")


class ProductCategory(enum.Enum):
    LAPTOPS = "laptops"
    PERIPHERALS = "peripherals"


def available_products_by_category(category: ProductCategory) -> ToolResult:
    products_by_category = {
        ProductCategory.LAPTOPS: ["Lenovo", "Dell"],
        ProductCategory.PERIPHERALS: ["Razer Keyboard", "Logitech Mouse"],
    }

    return ToolResult(products_by_category[category])


class Categories(enum.Enum):
    GRAPHICSCARD = "Graphics Card"
    PROCESSOR = "Processor"
    STORAGE = "Storage"
    POWER_SUPPLY = "Power Supply"
    MOTHERBOARD = "Motherboard"
    MEMORY = "Memory"
    CASE = "Case"
    CPUCOOLER = "CPU Cooler"
    MONITOR = "Monitor"
    KEYBOARD = "Keyboard"
    MOUSE = "Mouse"
    HEADSET = "Headset"
    AUDIO = "Audio"
    COOLING = "Cooling"
    ACCESSORIES = "Accessories"
    LIGHTING = "Lighting"
    NETWORKING = "Networking"
    LAPTOP = "Laptop"


# verify if product category is in stock
def get_in_stock(category: Categories) -> ToolResult:
    print(category.value)
    in_stock = []
    all_db = (
        supabase.table("products")
        .select("id, title, variant_inventory_qty")
        .eq("type", category.value)
        .execute()
    )

    for item in all_db.data:
        if item["variant_inventory_qty"] > 2:
            in_stock.append(item["variant_inventory_qty"])

    return ToolResult(len(in_stock) > 2)


# fetch products by tags
def get_products_by_tags(category: Categories, tags: str) -> ToolResult:
    tags_list = tags.split(",")
    products = []  # This will store unique products
    unique_ids = set()  # To track added product IDs

    for item in tags_list:
        item_db = (
            supabase.table("products")
            .select("id, title, variant_inventory_qty, variant_price, tags, body_html")
            .eq("type", category.value)
            .contains("tags", [item])
            .execute()
        )
        if item_db and item_db.data:
            for product in item_db.data:
                if product["id"] not in unique_ids:
                    unique_ids.add(product["id"])
                    products.append(product)

    return ToolResult(products)
