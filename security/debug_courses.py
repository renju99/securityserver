
import odoo
from odoo import api, SUPERUSER_ID

def check_courses():
    env = api.Environment(odoo.sql_db.db_connect('security').cursor(), SUPERUSER_ID, {})
    
    # Search for the course by name
    courses = env['slide.channel'].search([('name', 'ilike', 'Advanced Security Operations')])
    
    print(f"Found {len(courses)} courses matching 'Advanced Security Operations'")
    
    for course in courses:
        print(f"\nCourse ID: {course.id}")
        print(f"Name: {course.name}")
        print(f"XML ID: {course.get_external_id()}")
        print(f"Slide Count: {len(course.slide_ids)}")
        print(f"Slides: {[s.name for s in course.slide_ids]}")
        
if __name__ == "__main__":
    check_courses()
