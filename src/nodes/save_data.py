from src.state import GraphState
from src.storage import save_jobs, init_db

def save_data_node(state: GraphState) -> GraphState:
    """Final node to save results to SQLite."""
    if state["success"] and state["scraped_data"]:
        print(f"Successfully scraped {len(state['scraped_data'])} jobs for {state['company_name']}")
        
        # Initialize DB if not exists
        init_db()
        
        # Save to SQLite
        save_jobs(state["company_name"], [job.model_dump() for job in state["scraped_data"]])
        print(f"Results saved to jobs.db")
    else:
        print(f"No data saved for {state['company_name']}. Success: {state['success']}, Error: {state['error']}")
        
    return state
