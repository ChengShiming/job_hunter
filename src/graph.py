from langgraph.graph import StateGraph, END
from src.state import GraphState
from src.nodes.check_recipe import check_recipe_node
from src.nodes.discover_css import discover_css_node
from src.nodes.fast_scrape import fast_scrape_node
from src.nodes.save_data import save_data_node

def create_graph():
    workflow = StateGraph(GraphState)

    # Add Nodes
    workflow.add_node("check_recipe", check_recipe_node)
    workflow.add_node("discover_css", discover_css_node)
    workflow.add_node("fast_scrape", fast_scrape_node)
    workflow.add_node("save_data", save_data_node)

    # Set Entry Point
    workflow.set_entry_point("check_recipe")

    # Conditional Edges for check_recipe
    def after_check_recipe(state: GraphState):
        if state["recipe_config"]:
            return "fast_scrape"
        return "discover_css"

    workflow.add_conditional_edges(
        "check_recipe",
        after_check_recipe,
        {
            "fast_scrape": "fast_scrape",
            "discover_css": "discover_css"
        }
    )

    # After discover_css, go to fast_scrape if successful, else save_data
    def after_discover_css(state: GraphState):
        if state["success"] and state["recipe_config"]:
            return "fast_scrape"
        return "save_data"

    workflow.add_conditional_edges(
        "discover_css",
        after_discover_css,
        {
            "fast_scrape": "fast_scrape",
            "save_data": "save_data"
        }
    )

    # Conditional Edges for fast_scrape (Self-Healing)
    def after_fast_scrape(state: GraphState):
        if state["success"]:
            return "save_data"
        
        # If it failed and we haven't retried discovery
        if state["retry_count"] < 1:
            state["retry_count"] += 1
            return "discover_css"
        
        return "save_data"

    workflow.add_conditional_edges(
        "fast_scrape",
        after_fast_scrape,
        {
            "save_data": "save_data",
            "discover_css": "discover_css"
        }
    )
    
    # Save Data leads to END
    workflow.add_edge("save_data", END)

    return workflow.compile()
