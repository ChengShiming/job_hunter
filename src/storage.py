import sqlite3
import os
from typing import List, Dict

DB_PATH = "data/jobs.db"

def init_db():
    """Initializes the SQLite database and creates the jobs table."""
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            company TEXT,
            title TEXT,
            job_desc TEXT,
            job_requirements TEXT,
            location TEXT,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company, job_id, link)
        )
    """)
    # Add job_requirements column if upgrading from old schema
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN job_requirements TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()

def save_jobs(company: str, jobs: List[Dict]):
    """Saves a list of jobs to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for job in jobs:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO jobs (job_id, company, title, job_desc, job_requirements, location, link)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("job_id", ""),
                company,
                job.get("title", ""),
                job.get("job_desc", ""),
                job.get("job_requirements", ""),
                job.get("location", ""),
                job.get("link", "")
            ))
        except Exception as e:
            print(f"Error saving job: {e}")
            
    conn.commit()
    conn.close()
