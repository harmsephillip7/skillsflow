#!/usr/bin/env python
"""Test Moodle API connection and explore available data."""
import requests
import json
import sys

# Moodle credentials
MOODLE_URL = 'https://ecampus.uxieducation.co.za'
TOKEN = 'e74af13c2aeb40062548f8b4ee5cccd5'


def call_moodle(function, **params):
    """Call Moodle Web Services API."""
    url = f'{MOODLE_URL}/webservice/rest/server.php'
    params.update({
        'wstoken': TOKEN,
        'wsfunction': function,
        'moodlewsrestformat': 'json'
    })
    response = requests.get(url, params=params, timeout=30)
    return response.json()


def explore_grades():
    """Explore grade data from Moodle."""
    print('=' * 70)
    print('GRADE DATA EXPLORATION')
    print('=' * 70)
    
    # Get a course with enrolled users
    courses = call_moodle('core_course_get_courses')
    test_course = courses[1] if len(courses) > 1 else courses[0]
    course_id = test_course['id']
    
    print(f"\nCourse: {test_course['fullname']} (ID: {course_id})")
    
    # Get enrolled users
    enrolled = call_moodle('core_enrol_get_enrolled_users', courseid=course_id)
    if 'exception' in enrolled:
        print(f"Cannot get enrolled users: {enrolled.get('message')}")
        return
    
    print(f"Enrolled users: {len(enrolled)}")
    
    # Test grade items API for first few users
    for user in enrolled[:3]:
        user_id = user['id']
        print(f"\nUser: {user['fullname']} (ID: {user_id})")
        
        grade_items = call_moodle('gradereport_user_get_grade_items', 
                                  courseid=course_id, userid=user_id)
        
        print(f"  Response type: {type(grade_items)}")
        
        if isinstance(grade_items, dict):
            if 'exception' in grade_items:
                print(f"  Error: {grade_items.get('message', 'Unknown')}")
                continue
            
            user_grades = grade_items.get('usergrades', [])
            print(f"  Usergrades entries: {len(user_grades)}")
            
            for ug in user_grades:
                items = ug.get('gradeitems', [])
                print(f"  Grade items: {len(items)}")
                for item in items[:5]:
                    raw = item.get('graderaw')
                    formatted = item.get('gradeformatted', '-')
                    name = item.get('itemname', 'Unknown')[:40]
                    print(f"    [{item.get('id')}] {name}: raw={raw}, display={formatted}")


def explore_completion():
    """Explore completion data from Moodle."""
    print('\n' + '=' * 70)
    print('COMPLETION DATA EXPLORATION')
    print('=' * 70)
    
    courses = call_moodle('core_course_get_courses')
    test_course = courses[1] if len(courses) > 1 else courses[0]
    course_id = test_course['id']
    
    print(f"\nCourse: {test_course['fullname']} (ID: {course_id})")
    
    # Get enrolled users
    enrolled = call_moodle('core_enrol_get_enrolled_users', courseid=course_id)
    if 'exception' in enrolled or not enrolled:
        print("Cannot get enrolled users")
        return
    
    # Get completion status for first few users
    for user in enrolled[:5]:
        user_id = user['id']
        print(f"\n{user['fullname']} (ID: {user_id}):")
        
        # Course completion
        completion = call_moodle('core_completion_get_course_completion_status', 
                                  courseid=course_id, userid=user_id)
        if 'exception' not in completion:
            status = completion.get('completionstatus', {})
            completed = status.get('completed', False)
            print(f"  Course completed: {completed}")
            
            completions = status.get('completions', [])
            for c in completions[:5]:
                ctype = c.get('type', 'unknown')
                title = c.get('title', 'Unknown')
                complete = c.get('complete', False)
                print(f"    - [{ctype}] {title}: {'✓' if complete else '✗'}")
        else:
            print(f"  Cannot get completion: {completion.get('message', 'Error')}")


def explore_quizzes_and_assignments():
    """Explore quiz and assignment data."""
    print('\n' + '=' * 70)
    print('QUIZZES AND ASSIGNMENTS')
    print('=' * 70)
    
    courses = call_moodle('core_course_get_courses')
    course_ids = [c['id'] for c in courses[1:10]]  # First 9 real courses
    
    # Get quizzes
    quizzes = call_moodle('mod_quiz_get_quizzes_by_courses', courseids=course_ids)
    if 'exception' not in quizzes:
        quiz_list = quizzes.get('quizzes', [])
        print(f"\nQuizzes found: {len(quiz_list)}")
        for q in quiz_list[:15]:
            print(f"  [{q['id']}] {q['name'][:50]} (Course: {q['course']})")
            print(f"        Grade: {q.get('grade', 'N/A')} | Attempts: {q.get('attempts', 'N/A')}")
    
    # Get assignments
    assigns = call_moodle('mod_assign_get_assignments', courseids=course_ids)
    if 'exception' not in assigns:
        print(f"\nAssignments:")
        for course in assigns.get('courses', [])[:5]:
            print(f"\n  {course.get('fullname', '')[:50]}:")
            for a in course.get('assignments', [])[:5]:
                print(f"    [{a['id']}] {a['name'][:40]}")
                print(f"          Due: {a.get('duedate', 'No due date')}")


def list_all_qualifications():
    """List all qualifications (courses) that could be synced."""
    print('\n' + '=' * 70)
    print('ALL MOODLE COURSES (Potential Qualifications)')
    print('=' * 70)
    
    # Get categories first
    categories = call_moodle('core_course_get_categories')
    cat_map = {c['id']: c['name'] for c in categories}
    
    # Get courses
    courses = call_moodle('core_course_get_courses')
    
    print(f"\nTotal: {len(courses)} courses in {len(categories)} categories\n")
    
    # Group by category
    by_category = {}
    for c in courses:
        cat_id = c.get('categoryid', 0)
        cat_name = cat_map.get(cat_id, 'Uncategorized')
        if cat_name not in by_category:
            by_category[cat_name] = []
        by_category[cat_name].append(c)
    
    for cat_name in sorted(by_category.keys()):
        courses_in_cat = by_category[cat_name]
        print(f"\n{cat_name} ({len(courses_in_cat)} courses):")
        for c in courses_in_cat[:5]:
            print(f"  [{c['id']}] {c['fullname'][:55]}")
        if len(courses_in_cat) > 5:
            print(f"  ... and {len(courses_in_cat) - 5} more")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'grades':
            explore_grades()
        elif cmd == 'completion':
            explore_completion()
        elif cmd == 'quizzes':
            explore_quizzes_and_assignments()
        elif cmd == 'qualifications':
            list_all_qualifications()
        elif cmd == 'all':
            explore_grades()
            explore_completion()
            explore_quizzes_and_assignments()
            list_all_qualifications()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python test_moodle_api.py [grades|completion|quizzes|qualifications|all]")
        return

    # Default: Test 1: Get Site Info
    print('=' * 70)
    print('1. SITE INFORMATION')
    print('=' * 70)
    site_info = call_moodle('core_webservice_get_site_info')
    
    if 'exception' in site_info:
        print(f"Error: {site_info.get('message', site_info)}")
        return
    
    print(f"Site Name: {site_info.get('sitename')}")
    print(f"Username: {site_info.get('username')}")
    print(f"User ID: {site_info.get('userid')}")
    print(f"Full Name: {site_info.get('fullname')}")
    print(f"Moodle Version: {site_info.get('release')}")
    print(f"Site URL: {site_info.get('siteurl')}")
    
    # Show available functions
    functions = site_info.get('functions', [])
    print(f"\nAvailable API Functions: {len(functions)}")
    print("\nFunction Categories:")
    
    # Group functions by prefix
    categories = {}
    for func in functions:
        name = func.get('name', '')
        prefix = name.split('_')[0] if '_' in name else name
        if prefix not in categories:
            categories[prefix] = []
        categories[prefix].append(name)
    
    for cat in sorted(categories.keys()):
        print(f"  {cat}: {len(categories[cat])} functions")
    
    # Test 2: Get Courses
    print('\n' + '=' * 70)
    print('2. AVAILABLE COURSES')
    print('=' * 70)
    courses = call_moodle('core_course_get_courses')
    
    if 'exception' in courses:
        print(f"Error: {courses.get('message', 'Could not fetch courses')}")
    else:
        print(f"Total Courses: {len(courses)}")
        for course in courses[:15]:  # Show first 15 courses
            print(f"  [{course.get('id')}] {course.get('fullname')}")
            if course.get('shortname'):
                print(f"      Short: {course.get('shortname')}")
        if len(courses) > 15:
            print(f"  ... and {len(courses) - 15} more courses")
    
    # Test 3: Get Categories
    print('\n' + '=' * 70)
    print('3. COURSE CATEGORIES')
    print('=' * 70)
    categories_data = call_moodle('core_course_get_categories')
    
    if 'exception' in categories_data:
        print(f"Error: {categories_data.get('message', 'Could not fetch categories')}")
    else:
        print(f"Total Categories: {len(categories_data)}")
        for cat in categories_data[:20]:
            depth = '  ' * cat.get('depth', 0)
            print(f"  {depth}[{cat.get('id')}] {cat.get('name')}")
    
    # Test 4: Get Users (if we have permission)
    print('\n' + '=' * 70)
    print('4. USER DATA ACCESS')
    print('=' * 70)
    
    # Try to get users
    users = call_moodle('core_user_get_users', criteria=[{'key': 'email', 'value': '%'}])
    if 'exception' in users:
        print(f"User search: {users.get('message', 'Limited access')}")
    else:
        user_list = users.get('users', [])
        print(f"Can access user data: Yes ({len(user_list)} users found)")
    
    # Test 5: List all available API functions
    print('\n' + '=' * 70)
    print('5. AVAILABLE API FUNCTIONS (Grouped)')
    print('=' * 70)
    
    useful_functions = [
        # User functions
        'core_user_get_users',
        'core_user_get_users_by_field',
        'core_user_create_users',
        'core_user_update_users',
        # Course functions
        'core_course_get_courses',
        'core_course_get_contents',
        'core_course_get_categories',
        'core_course_get_enrolled_courses_by_timeline_classification',
        # Enrollment functions
        'core_enrol_get_enrolled_users',
        'enrol_manual_enrol_users',
        'enrol_manual_unenrol_users',
        # Grade functions
        'gradereport_user_get_grades_table',
        'gradereport_user_get_grade_items',
        'core_grades_get_grades',
        # Assignment functions
        'mod_assign_get_assignments',
        'mod_assign_get_grades',
        'mod_assign_get_submissions',
        # Quiz functions
        'mod_quiz_get_quizzes_by_courses',
        'mod_quiz_get_user_attempts',
        # Completion functions
        'core_completion_get_activities_completion_status',
        'core_completion_get_course_completion_status',
    ]
    
    available = [f.get('name') for f in site_info.get('functions', [])]
    
    print("\nKey Functions Status:")
    for func in useful_functions:
        status = "✓" if func in available else "✗"
        print(f"  {status} {func}")
    
    # Test 6: Sample Course Content
    print('\n' + '=' * 70)
    print('6. SAMPLE COURSE CONTENT')
    print('=' * 70)
    
    if courses and len(courses) > 1:
        # Get first non-site course
        test_course = courses[1] if len(courses) > 1 else courses[0]
        course_id = test_course.get('id')
        print(f"\nSample: {test_course.get('fullname')} (ID: {course_id})")
        
        contents = call_moodle('core_course_get_contents', courseid=course_id)
        if 'exception' in contents:
            print(f"  Error: {contents.get('message')}")
        else:
            print(f"  Sections: {len(contents)}")
            for section in contents[:5]:
                print(f"    - {section.get('name', 'Unnamed Section')}")
                modules = section.get('modules', [])
                for mod in modules[:3]:
                    print(f"        • {mod.get('modname')}: {mod.get('name')}")
    
    # Test 7: Enrolled Users in a Course
    print('\n' + '=' * 70)
    print('7. ENROLLED USERS (Sample)')
    print('=' * 70)
    
    if courses and len(courses) > 1:
        test_course = courses[1] if len(courses) > 1 else courses[0]
        course_id = test_course.get('id')
        
        enrolled = call_moodle('core_enrol_get_enrolled_users', courseid=course_id)
        if 'exception' in enrolled:
            print(f"  Error: {enrolled.get('message')}")
        else:
            print(f"  Course: {test_course.get('fullname')}")
            print(f"  Enrolled Users: {len(enrolled)}")
            for user in enrolled[:10]:
                roles = ', '.join([r.get('shortname', '') for r in user.get('roles', [])])
                print(f"    - {user.get('fullname')} ({user.get('email')}) - {roles}")
            if len(enrolled) > 10:
                print(f"    ... and {len(enrolled) - 10} more users")


if __name__ == '__main__':
    main()
