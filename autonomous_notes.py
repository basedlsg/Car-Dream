#!/usr/bin/env python

def generate_autonomous_note(location, action, next_poi):
    """Generates a short autonomous note."""
    note = f"At {location}, did {action} to reach {next_poi}."
    return note

# Example usage
location = "Intersection A"
action = "turned left"
next_poi = "Building B"
note = generate_autonomous_note(location, action, next_poi)
print(note)