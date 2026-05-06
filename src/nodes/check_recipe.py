import json
from pathlib import Path
from typing import Optional, Dict
from src.state import GraphState

RECIPES_DIR = Path("data/recipes")

def get_recipe_path(company_name: str) -> Path:
    """Returns the path to the {company}.json for a given company."""
    return RECIPES_DIR / f"{company_name}.json"

def recipe_exists(company_name: str) -> bool:
    """Checks if a JSON recipe exists for a given company."""
    return get_recipe_path(company_name).exists()

def read_recipe(company_name: str) -> Optional[Dict]:
    """Reads the JSON recipe for a company."""
    path = get_recipe_path(company_name)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading recipe for {company_name}: {e}")
    return None

def save_recipe(company_name: str, recipe_data: Dict):
    """Saves the recipe data to a JSON file."""
    path = get_recipe_path(company_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(recipe_data, f, ensure_ascii=False, indent=2)

def check_recipe_node(state: GraphState) -> GraphState:
    """Checks if a JSON recipe exists for the company."""
    company_name = state["company_name"]
    
    if recipe_exists(company_name):
        recipe = read_recipe(company_name)
        state["recipe_config"] = recipe
        state["url"] = recipe.get("url")
        print(f"Found existing recipe for {company_name}")
    else:
        state["recipe_config"] = None
        print(f"No existing recipe for {company_name}")
        
    return state
