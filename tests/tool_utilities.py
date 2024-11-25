import enum
import os
from supabase import create_client

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


class ProductType(enum.Enum):
    DRINKS = "drinks"
    TOPPINGS = "toppings"


def get_available_product_by_type(product_type: ProductType) -> ToolResult:
    if product_type == ProductType.DRINKS:
        return get_available_drinks()
    elif product_type == ProductType.TOPPINGS:
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


def recommend_drink(user_is_adult: bool) -> ToolResult:
    if user_is_adult:
        return ToolResult("Beer")
    else:
        return ToolResult("Soda")


def check_username_validity(name: str) -> ToolResult:
    return ToolResult(name != "Dukie")


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


class Tags(enum.Enum):
    GENERAL = "general"
    GAMING = "gaming"
    DISPLAYS = "displays"
    GRAPHICS = "graphics"
    COOLING = "cooling"
    STORAGE = "storage"
    CONNECTIVITY = "connectivity"
    POWER = "power"
    PERIPHERALS = "peripherals"
    LAPTOPS = "laptops"
    DESKS_AND_MOUNTS = "desks and mounts"
    CONTENT_CREATION = "content creation"
    MISC = "miscellaneous"


TAG_VALUES = {
    Tags.GENERAL: [
        "storage",
        "portable",
        "external",
        "productivity",
        "office",
        "business",
        "professional",
        "mainstream",
        "creative",
        "studio",
    ],
    Tags.GAMING: [
        "gaming",
        "mechanical",
        "premium",
        "budget",
        "rgb",
        "lightweight",
        "tenkeyless",
        "compact",
        "ergonomic",
        "control",
        "customization",
    ],
    Tags.DISPLAYS: [
        "monitor",
        "curved",
        "4k",
        "144hz",
        "hdmi2.1",
        "ips",
        "eye-care",
        "quantum-dot",
        "calibration",
    ],
    Tags.GRAPHICS: [
        "nvidia",
        "amd",
        "intel",
        "high-end",
        "high-performance",
        "rtx4090",
        "rtx4080",
        "rtx4070",
        "rtx4060ti",
        "rtx4060",
        "rtx4050",
        "rtx3050",
        "rtx3050ti",
        "rx6600",
        "z690",
        "ddr5",
        "ddr4",
    ],
    Tags.COOLING: ["cooling", "aio", "liquid-cooler", "case", "atx", "fans"],
    Tags.STORAGE: ["ssd", "nvme", "hdd", "sata"],
    Tags.CONNECTIVITY: ["wifi", "usb", "usb-c", "hdmi", "connectivity", "hub", "dock"],
    Tags.POWER: ["psu", "modular", "gold-rated", "power", "protection", "surge"],
    Tags.PERIPHERALS: [
        "mousepad",
        "desk-pad",
        "keyboard",
        "speakers",
        "microphone",
        "audio",
        "dac",
        "lighting",
    ],
    Tags.LAPTOPS: ["laptop", "ultrabook", "convertible", "macbook", "m3"],
    Tags.DESKS_AND_MOUNTS: ["desk", "mount"],
    Tags.CONTENT_CREATION: ["streaming", "capture", "content-creation", "interface"],
    Tags.MISC: ["bluetooth", "comfort", "modding"],
}


def get_product_tags(category: Categories, tags: Tags) -> ToolResult:
    """Get relevant tags of the product"""
    return ToolResult(TAG_VALUES[tags])


def get_products_by_tags(category: Categories, tags: str) -> ToolResult:
    """Gets list a products by tags"""
    tags_list = tags.split(",")
    unique_products = {}

    for tag in tags_list:
        item_db = (
            supabase.table("products")
            .select("id, title, variant_inventory_qty, variant_price, tags, body_html")
            .eq("type", category.value)
            .contains("tags", [tag])
            .execute()
        )
        if item_db and item_db.data:
            for product in item_db.data:
                unique_products[product["id"]] = product

    return ToolResult(list(unique_products.values()))
