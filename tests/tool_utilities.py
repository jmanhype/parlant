# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum
from typing import Optional
import json

from parlant.core.tools import ToolResult


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
    GENERAL = "General"
    GAMING = "Gaming"
    DISPLAYS = "Displays"
    GRAPHICS = "Graphics"
    COOLING = "Cooling"
    STORAGE = "Storage"
    CONNECTIVITY = "Connectivity"
    POWER = "Power"
    PERIPHERALS = "Peripherals"
    LAPTOPS = "Laptops"
    DESKS_AND_MOUNTS = "Desks and mounts"
    CONTENT_CREATION = "Content creation"
    MISC = "Miscellaneous"


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


file_path = "tests/core/data/tech_products.json"

with open(file_path, "r") as file:
    tech_products = json.load(file)


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


def get_available_soups() -> ToolResult:
    return ToolResult("['Tomato', 'Turpolance', 'Pumpkin', 'Turkey Soup', 'Tom Yum', 'Onion']")


def fetch_account_balance() -> ToolResult:
    return ToolResult(data={"balance": 1000.0})


def get_keyleth_stamina() -> ToolResult:
    return ToolResult(data=100.0)


def consult_policy() -> ToolResult:
    policies = {
        "return_policy": "The return policy allows returns within 4 days and 4 hours from the time of purchase.",
        "warranty_policy": "All products come with a 1-year warranty.",
    }
    return ToolResult(policies)


def other_inquiries() -> ToolResult:
    return ToolResult("Sorry, we could not find a specific answer to your query.")


def try_unlock_card(last_6_digits: Optional[str] = None) -> ToolResult:
    try:
        if not last_6_digits:
            return ToolResult({"failure": "need to specify the last 6 digits of the card"})
        return ToolResult({"success": "card succesfuly unlocked"})
    except BaseException:
        return ToolResult({"failure": "system error"})


def is_product_category_in_stock(category: Categories) -> ToolResult:
    products = [item for item in tech_products if item["type"].lower() == category.value.lower()]
    qty = sum(item["qty"] for item in products)
    return ToolResult(qty)

def get_products_by_tags(category: Categories, tags: Tags) -> ToolResult:
    return ToolResult(TAG_VALUES[tags])
