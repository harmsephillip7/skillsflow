"""
Moodle Web Services API Client
Handles authentication and communication with Moodle LMS instances.
"""
import requests
from typing import Dict, List, Optional, Any
from django.utils import timezone
from ..models import MoodleInstance


class MoodleAPIError(Exception):
    """Custom exception for Moodle API errors"""
    pass


class MoodleClient:
    """
    Client for interacting with Moodle Web Services API.
    
    Usage:
        # Using MoodleInstance model
        client = MoodleClient(moodle_instance)
        
        # Using direct URL and token
        client = MoodleClient(base_url='https://moodle.example.com', token='xxx')
        
        if client.test_connection():
            courses = client.get_courses()
    """
    
    def __init__(self, instance: MoodleInstance = None, base_url: str = None, token: str = None):
        """
        Initialize Moodle client with instance configuration or direct credentials.
        
        Args:
            instance: MoodleInstance model with base_url and ws_token
            base_url: Direct Moodle URL (alternative to instance)
            token: Direct API token (alternative to instance)
        """
        if instance:
            self.instance = instance
            self.base_url = instance.base_url.rstrip('/')
            self.ws_token = instance.ws_token
        elif base_url and token:
            self.instance = None
            self.base_url = base_url.rstrip('/')
            self.ws_token = token
        else:
            raise ValueError("Either instance or both base_url and token required")
        
        self.api_endpoint = f"{self.base_url}/webservice/rest/server.php"
    
    def _make_request(
        self,
        function: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Moodle Web Services API.
        
        Args:
            function: Moodle web service function name
            params: Additional parameters for the function
        
        Returns:
            JSON response from Moodle API
        
        Raises:
            MoodleAPIError: If API returns error or connection fails
        """
        payload = {
            'wstoken': self.ws_token,
            'wsfunction': function,
            'moodlewsrestformat': 'json'
        }
        
        if params:
            payload.update(params)
        
        try:
            response = requests.post(
                self.api_endpoint,
                data=payload,
                timeout=60  # Increased timeout for larger operations
            )
            response.raise_for_status()
            data = response.json()
            
            # Check for Moodle-specific errors
            if isinstance(data, dict) and 'exception' in data:
                error_msg = data.get('message', 'Unknown Moodle error')
                raise MoodleAPIError(f"Moodle API Error: {error_msg}")
            
            return data
            
        except requests.exceptions.Timeout:
            raise MoodleAPIError("Connection timeout - Moodle server not responding")
        except requests.exceptions.ConnectionError:
            raise MoodleAPIError("Cannot connect to Moodle server - check base URL")
        except requests.exceptions.HTTPError as e:
            raise MoodleAPIError(f"HTTP error {e.response.status_code}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise MoodleAPIError(f"Request failed: {str(e)}")
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to Moodle instance.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            site_info = self.get_site_info()
            site_name = site_info.get('sitename', 'Unknown')
            version = site_info.get('release', 'Unknown')
            return True, f"Connected to {site_name} (Moodle {version})"
        except MoodleAPIError as e:
            return False, str(e)
    
    def get_site_info(self) -> Dict[str, Any]:
        """
        Get Moodle site information.
        
        Returns:
            Site info including sitename, release, version, functions
        """
        return self._make_request('core_webservice_get_site_info')
    
    def get_courses(self) -> List[Dict[str, Any]]:
        """
        Get all courses accessible to the authenticated user.
        
        Returns:
            List of course dictionaries with id, shortname, fullname, etc.
        """
        result = self._make_request('core_course_get_courses')
        return result if isinstance(result, list) else []
    
    def get_course_contents(self, course_id: int) -> List[Dict[str, Any]]:
        """
        Get course contents including sections and activities.
        
        Args:
            course_id: Moodle course ID
        
        Returns:
            List of course sections with modules/activities
        """
        result = self._make_request(
            'core_course_get_contents',
            {'courseid': course_id}
        )
        return result if isinstance(result, list) else []
    
    def get_enrolled_users(self, course_id: int) -> List[Dict[str, Any]]:
        """
        Get users enrolled in a course.
        
        Args:
            course_id: Moodle course ID
        
        Returns:
            List of enrolled users with id, username, email, fullname
        """
        result = self._make_request(
            'core_enrol_get_enrolled_users',
            {'courseid': course_id}
        )
        return result if isinstance(result, list) else []
    
    def get_user_grades(
        self,
        course_id: int,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get grades for a course (optionally filtered by user).
        
        Args:
            course_id: Moodle course ID
            user_id: Optional Moodle user ID to filter grades
        
        Returns:
            List of grade items with user grades
        """
        params = {'courseid': course_id}
        if user_id:
            params['userid'] = user_id
        
        result = self._make_request('gradereport_user_get_grade_items', params)
        
        # Handle different response structures
        if isinstance(result, dict):
            return result.get('usergrades', [])
        return result if isinstance(result, list) else []
    
    def get_assignment_grades(self, assignment_id: int) -> List[Dict[str, Any]]:
        """
        Get grades for a specific assignment.
        
        Args:
            assignment_id: Moodle assignment ID
        
        Returns:
            List of assignment grades
        """
        result = self._make_request(
            'mod_assign_get_grades',
            {'assignmentids[0]': assignment_id}
        )
        
        if isinstance(result, dict):
            return result.get('assignments', [{}])[0].get('grades', [])
        return []
    
    def enroll_user(
        self,
        course_id: int,
        user_id: int,
        role_id: int = 5  # Default: Student role
    ) -> bool:
        """
        Enroll a user in a course.
        
        Args:
            course_id: Moodle course ID
            user_id: Moodle user ID
            role_id: Moodle role ID (5 = Student, 3 = Teacher)
        
        Returns:
            True if enrollment successful
        """
        try:
            self._make_request(
                'enrol_manual_enrol_users',
                {
                    'enrolments[0][roleid]': role_id,
                    'enrolments[0][userid]': user_id,
                    'enrolments[0][courseid]': course_id
                }
            )
            return True
        except MoodleAPIError:
            return False
    
    def create_user(
        self,
        username: str,
        password: str,
        firstname: str,
        lastname: str,
        email: str
    ) -> Optional[int]:
        """
        Create a new user in Moodle.
        
        Args:
            username: Unique username
            password: User password
            firstname: First name
            lastname: Last name
            email: Email address
        
        Returns:
            New user ID if successful, None otherwise
        """
        try:
            result = self._make_request(
                'core_user_create_users',
                {
                    'users[0][username]': username,
                    'users[0][password]': password,
                    'users[0][firstname]': firstname,
                    'users[0][lastname]': lastname,
                    'users[0][email]': email
                }
            )
            
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('id')
            return None
            
        except MoodleAPIError:
            return None

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get all course categories.
        
        Returns:
            List of categories with id, name, parent, depth
        """
        result = self._make_request('core_course_get_categories')
        return result if isinstance(result, list) else []

    def get_course_completion_status(
        self,
        course_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Get course completion status for a user.
        
        Args:
            course_id: Moodle course ID
            user_id: Moodle user ID
        
        Returns:
            Completion status with completed flag and activity completions
        """
        result = self._make_request(
            'core_completion_get_course_completion_status',
            {'courseid': course_id, 'userid': user_id}
        )
        return result if isinstance(result, dict) else {}

    def get_quizzes(self, course_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get quizzes for specified courses.
        
        Args:
            course_ids: List of Moodle course IDs
        
        Returns:
            List of quizzes
        """
        params = {f'courseids[{i}]': cid for i, cid in enumerate(course_ids)}
        result = self._make_request('mod_quiz_get_quizzes_by_courses', params)
        
        if isinstance(result, dict):
            return result.get('quizzes', [])
        return result if isinstance(result, list) else []

    def get_assignments(self, course_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get assignments for specified courses.
        
        Args:
            course_ids: List of Moodle course IDs
        
        Returns:
            List of course assignment data
        """
        params = {f'courseids[{i}]': cid for i, cid in enumerate(course_ids)}
        result = self._make_request('mod_assign_get_assignments', params)
        
        if isinstance(result, dict):
            return result.get('courses', [])
        return result if isinstance(result, list) else []
    
    def update_last_sync(self):
        """Update the instance's last sync timestamp"""
        if self.instance:
            self.instance.last_sync = timezone.now()
            self.instance.save(update_fields=['last_sync'])

