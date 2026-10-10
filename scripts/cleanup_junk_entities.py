#!/usr/bin/env python3
import sys
import os

# Add backend to path so we can import utils
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from utils.tag_patterns import validate_and_parse_tag, is_valid_location_or_person
from database.neo4j_client import get_neo4j_driver

def cleanup_junk_entities(dry_run: bool = True):
    """
    Cleans up junk entities from Neo4j that fail the new tag/name validation.
    """
    driver = get_neo4j_driver()
    
    print(f"Starting cleanup (dry_run={dry_run})")
    
    deleted_assets = 0
    deleted_locations = 0
    deleted_people = 0
    
    with driver.session() as session:
        # 1. Cleanup Assets
        print("\n--- Assets ---")
        result = session.run("MATCH (a:Asset) RETURN a.id AS id, a.canonical_name AS name, a.tag AS tag")
        for record in result:
            node_id = record["id"]
            name = record["name"]
            tag = record["tag"]
            
            # The canonical name for assets should be the tag
            val_text = tag or name
            if not validate_and_parse_tag(val_text):
                print(f"Junk Asset: {name} (id: {node_id})")
                if not dry_run:
                    session.run("MATCH (a:Asset {id: $id}) DETACH DELETE a", id=node_id)
                deleted_assets += 1
                
        # 2. Cleanup Locations
        print("\n--- Locations ---")
        result = session.run("MATCH (l:Location) RETURN l.id AS id, l.canonical_name AS name")
        for record in result:
            node_id = record["id"]
            name = record["name"]
            
            if not is_valid_location_or_person(name):
                print(f"Junk Location: {name} (id: {node_id})")
                if not dry_run:
                    session.run("MATCH (l:Location {id: $id}) DETACH DELETE l", id=node_id)
                deleted_locations += 1
                
        # 3. Cleanup People
        print("\n--- People ---")
        result = session.run("MATCH (p:Person) RETURN p.id AS id, p.canonical_name AS name")
        for record in result:
            node_id = record["id"]
            name = record["name"]
            
            if not is_valid_location_or_person(name):
                print(f"Junk Person: {name} (id: {node_id})")
                if not dry_run:
                    session.run("MATCH (p:Person {id: $id}) DETACH DELETE p", id=node_id)
                deleted_people += 1
                
    print("\n--- Summary ---")
    print(f"Assets to delete: {deleted_assets}")
    print(f"Locations to delete: {deleted_locations}")
    print(f"People to delete: {deleted_people}")
    if dry_run:
        print("This was a DRY RUN. Run with --execute to actually delete.")
        
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually delete nodes (no dry run)")
    args = parser.parse_args()
    
    cleanup_junk_entities(dry_run=not args.execute)
