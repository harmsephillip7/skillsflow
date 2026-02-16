"""
Meeting Invite Utilities for Training Committee Meetings

Provides:
- ICS calendar file generation (compatible with Outlook, Google Calendar, Apple Calendar)
- Zoom meeting creation via API
- Email notifications with ICS attachments
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
import requests
import base64
import json


class ICSGenerator:
    """
    Generate ICS (iCalendar) files for meeting invites.
    Compatible with Outlook, Google Calendar, and Apple Calendar.
    """
    
    def __init__(self, meeting):
        """
        Initialize with a TrainingCommitteeMeeting instance.
        """
        self.meeting = meeting
    
    def generate_uid(self) -> str:
        """Generate a unique identifier for the calendar event."""
        unique_string = f"{self.meeting.id}-{self.meeting.scheduled_date}-{self.meeting.committee.client.id}"
        return hashlib.md5(unique_string.encode()).hexdigest() + "@skillsflow.co.za"
    
    def format_datetime(self, dt: datetime) -> str:
        """Format datetime for ICS format (YYYYMMDDTHHMMSSZ)."""
        # Convert to UTC
        if timezone.is_aware(dt):
            dt = dt.astimezone(timezone.utc)
        return dt.strftime('%Y%m%dT%H%M%SZ')
    
    def escape_text(self, text: str) -> str:
        """Escape special characters in ICS text fields."""
        if not text:
            return ''
        # Escape backslashes, semicolons, commas, and newlines
        text = text.replace('\\', '\\\\')
        text = text.replace(';', '\\;')
        text = text.replace(',', '\\,')
        text = text.replace('\n', '\\n')
        return text
    
    def fold_line(self, line: str, max_length: int = 75) -> str:
        """Fold long lines according to ICS spec (max 75 chars)."""
        if len(line) <= max_length:
            return line
        
        result = []
        while len(line) > max_length:
            result.append(line[:max_length])
            line = ' ' + line[max_length:]  # Continuation lines start with space
        result.append(line)
        return '\r\n'.join(result)
    
    def build_description(self) -> str:
        """Build the meeting description with agenda items."""
        lines = []
        
        # Meeting details
        lines.append(f"Meeting: {self.meeting.title}")
        lines.append(f"Client: {self.meeting.committee.client.company_name}")
        lines.append("")
        
        # Location/link
        if self.meeting.meeting_type == 'VIRTUAL':
            lines.append("This is a virtual meeting.")
            if self.meeting.meeting_link:
                lines.append(f"Join Link: {self.meeting.meeting_link}")
            if self.meeting.meeting_id:
                lines.append(f"Meeting ID: {self.meeting.meeting_id}")
            if self.meeting.meeting_password:
                lines.append(f"Password: {self.meeting.meeting_password}")
        elif self.meeting.meeting_type == 'HYBRID':
            lines.append("This is a hybrid meeting.")
            if self.meeting.location:
                lines.append(f"In-Person Location: {self.meeting.location}")
            if self.meeting.meeting_link:
                lines.append(f"Join Link: {self.meeting.meeting_link}")
        else:
            if self.meeting.location:
                lines.append(f"Location: {self.meeting.location}")
        
        lines.append("")
        
        # Agenda
        agenda_items = self.meeting.tc_agenda_items.all().order_by('sequence')
        if agenda_items.exists():
            lines.append("AGENDA:")
            lines.append("-" * 40)
            for item in agenda_items:
                lines.append(f"{item.sequence}. {item.title} ({item.duration_minutes} min)")
                if item.description:
                    lines.append(f"   {item.description}")
            lines.append("")
        
        # Notes
        if self.meeting.notes:
            lines.append("Notes:")
            lines.append(self.meeting.notes)
        
        return '\n'.join(lines)
    
    def generate(self, method: str = 'REQUEST') -> str:
        """
        Generate the ICS file content.
        
        Args:
            method: ICS method - REQUEST for new invite, CANCEL for cancellation
        
        Returns:
            ICS file content as string
        """
        # Calculate times
        start_dt = timezone.make_aware(
            datetime.combine(self.meeting.scheduled_date, self.meeting.scheduled_time)
        )
        end_dt = start_dt + timedelta(minutes=self.meeting.duration_minutes)
        now = timezone.now()
        
        # Build location string
        location = self.meeting.location or ''
        if self.meeting.meeting_link and not location:
            location = self.meeting.meeting_link
        
        # Build attendee list
        attendees = []
        for attendance in self.meeting.tc_attendance_records.select_related('member', 'member__contact'):
            member = attendance.member
            email = member.display_email
            name = member.display_name
            if email:
                attendees.append((email, name))
        
        # Build ICS content
        lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//SkillsFlow//Training Committee//EN',
            'CALSCALE:GREGORIAN',
            f'METHOD:{method}',
            'BEGIN:VEVENT',
            f'UID:{self.generate_uid()}',
            f'DTSTAMP:{self.format_datetime(now)}',
            f'DTSTART:{self.format_datetime(start_dt)}',
            f'DTEND:{self.format_datetime(end_dt)}',
            f'SUMMARY:{self.escape_text(self.meeting.title)}',
        ]
        
        # Add description
        description = self.build_description()
        lines.append(self.fold_line(f'DESCRIPTION:{self.escape_text(description)}'))
        
        # Add location
        if location:
            lines.append(f'LOCATION:{self.escape_text(location)}')
        
        # Add organizer
        if self.meeting.organized_by:
            organizer_email = self.meeting.organized_by.email
            organizer_name = self.meeting.organized_by.get_full_name() or self.meeting.organized_by.username
            lines.append(f'ORGANIZER;CN={self.escape_text(organizer_name)}:mailto:{organizer_email}')
        
        # Add attendees
        for email, name in attendees:
            lines.append(f'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN={self.escape_text(name)}:mailto:{email}')
        
        # Add alarm (reminder 1 day before)
        lines.extend([
            'BEGIN:VALARM',
            'ACTION:DISPLAY',
            'DESCRIPTION:Meeting Reminder',
            'TRIGGER:-P1D',
            'END:VALARM',
        ])
        
        # Add second alarm (1 hour before)
        lines.extend([
            'BEGIN:VALARM',
            'ACTION:DISPLAY',
            'DESCRIPTION:Meeting Starting Soon',
            'TRIGGER:-PT1H',
            'END:VALARM',
        ])
        
        lines.extend([
            'END:VEVENT',
            'END:VCALENDAR',
        ])
        
        return '\r\n'.join(lines)
    
    def generate_cancellation(self) -> str:
        """Generate an ICS cancellation notice."""
        return self.generate(method='CANCEL')


class ZoomIntegration:
    """
    Zoom API integration for creating meeting links.
    
    Requires ZOOM_JWT_TOKEN or ZOOM_OAUTH settings.
    """
    
    API_BASE_URL = 'https://api.zoom.us/v2'
    
    def __init__(self):
        self.jwt_token = getattr(settings, 'ZOOM_JWT_TOKEN', None)
        self.oauth_token = getattr(settings, 'ZOOM_OAUTH_TOKEN', None)
        self.user_id = getattr(settings, 'ZOOM_USER_ID', 'me')
    
    @property
    def is_configured(self) -> bool:
        """Check if Zoom integration is configured."""
        return bool(self.jwt_token or self.oauth_token)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        token = self.oauth_token or self.jwt_token
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
    
    def create_meeting(
        self,
        topic: str,
        start_time: datetime,
        duration_minutes: int,
        agenda: str = '',
        timezone_str: str = 'Africa/Johannesburg',
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Zoom meeting.
        
        Returns:
            Dictionary with meeting details including join_url, id, password
            or None if creation fails.
        """
        if not self.is_configured:
            return None
        
        # Format start time for Zoom API
        start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        payload = {
            'topic': topic,
            'type': 2,  # Scheduled meeting
            'start_time': start_time_str,
            'duration': duration_minutes,
            'timezone': timezone_str,
            'agenda': agenda[:2000] if agenda else '',  # Zoom has 2000 char limit
            'settings': {
                'host_video': True,
                'participant_video': True,
                'join_before_host': False,
                'mute_upon_entry': True,
                'waiting_room': True,
                'meeting_authentication': False,
            }
        }
        
        try:
            response = requests.post(
                f'{self.API_BASE_URL}/users/{self.user_id}/meetings',
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    'id': str(data.get('id', '')),
                    'join_url': data.get('join_url', ''),
                    'password': data.get('password', ''),
                    'host_url': data.get('start_url', ''),
                }
            else:
                # Log the error but don't raise
                print(f"Zoom API error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"Zoom API request failed: {e}")
            return None
    
    def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a Zoom meeting."""
        if not self.is_configured:
            return False
        
        try:
            response = requests.delete(
                f'{self.API_BASE_URL}/meetings/{meeting_id}',
                headers=self._get_headers(),
                timeout=30
            )
            return response.status_code == 204
        except requests.RequestException:
            return False
    
    def update_meeting(
        self,
        meeting_id: str,
        topic: str = None,
        start_time: datetime = None,
        duration_minutes: int = None,
    ) -> bool:
        """Update an existing Zoom meeting."""
        if not self.is_configured:
            return False
        
        payload = {}
        if topic:
            payload['topic'] = topic
        if start_time:
            payload['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        if duration_minutes:
            payload['duration'] = duration_minutes
        
        if not payload:
            return True  # Nothing to update
        
        try:
            response = requests.patch(
                f'{self.API_BASE_URL}/meetings/{meeting_id}',
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            return response.status_code == 204
        except requests.RequestException:
            return False


class MeetingInviteService:
    """
    Service for sending meeting invites with ICS attachments.
    """
    
    def __init__(self, meeting):
        """
        Initialize with a TrainingCommitteeMeeting instance.
        """
        self.meeting = meeting
        self.ics_generator = ICSGenerator(meeting)
        self.zoom = ZoomIntegration()
    
    def create_zoom_meeting(self) -> bool:
        """
        Create a Zoom meeting for this Training Committee meeting.
        Updates the meeting with Zoom details.
        
        Returns:
            True if successful, False otherwise.
        """
        if not self.meeting.committee.include_zoom_link:
            return False
        
        if not self.zoom.is_configured:
            return False
        
        # Build agenda text
        agenda_lines = []
        for item in self.meeting.tc_agenda_items.order_by('sequence'):
            agenda_lines.append(f"{item.sequence}. {item.title}")
        
        start_dt = datetime.combine(
            self.meeting.scheduled_date,
            self.meeting.scheduled_time
        )
        
        zoom_data = self.zoom.create_meeting(
            topic=f"{self.meeting.committee.client.company_name} - {self.meeting.title}",
            start_time=start_dt,
            duration_minutes=self.meeting.duration_minutes,
            agenda='\n'.join(agenda_lines),
        )
        
        if zoom_data:
            self.meeting.meeting_link = zoom_data['join_url']
            self.meeting.meeting_id = zoom_data['id']
            self.meeting.meeting_password = zoom_data.get('password', '')
            self.meeting.save(update_fields=['meeting_link', 'meeting_id', 'meeting_password'])
            return True
        
        return False
    
    def send_invites(
        self,
        subject_prefix: str = '',
        include_ics: bool = True,
        include_zoom: bool = True,
    ) -> Dict[str, Any]:
        """
        Send meeting invites to all committee members.
        
        Returns:
            Dictionary with send results.
        """
        from corporate.models import MeetingAttendance
        
        # Create Zoom meeting if needed
        if include_zoom and self.meeting.committee.include_zoom_link:
            if not self.meeting.meeting_link:
                self.create_zoom_meeting()
        
        # Generate ICS content
        ics_content = self.ics_generator.generate() if include_ics else None
        
        # Get recipients
        tc_attendance_records = self.meeting.tc_attendance_records.select_related(
            'member', 'member__contact'
        ).filter(member__receives_meeting_invites=True)
        
        sent_count = 0
        failed_count = 0
        errors = []
        
        for attendance in tc_attendance_records:
            member = attendance.member
            email = member.display_email
            
            if not email:
                failed_count += 1
                errors.append(f"No email for {member.display_name}")
                continue
            
            # Build subject
            subject = f"{subject_prefix}Meeting Invite: {self.meeting.title} - {self.meeting.scheduled_date.strftime('%d %B %Y')}"
            
            # Render email templates
            context = {
                'meeting': self.meeting,
                'member': member,
                'client': self.meeting.committee.client,
                'agenda_items': self.meeting.tc_agenda_items.order_by('sequence'),
            }
            
            text_content = render_to_string('corporate/emails/meeting_invite.txt', context)
            html_content = render_to_string('corporate/emails/meeting_invite.html', context)
            
            try:
                # Create email
                email_message = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_message.attach_alternative(html_content, 'text/html')
                
                # Attach ICS file
                if ics_content:
                    email_message.attach(
                        'meeting.ics',
                        ics_content,
                        'text/calendar; method=REQUEST'
                    )
                
                # Send
                email_message.send(fail_silently=False)
                
                # Update attendance record
                attendance.invite_sent = True
                attendance.invite_sent_date = timezone.now()
                attendance.save(update_fields=['invite_sent', 'invite_sent_date'])
                
                sent_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to send to {email}: {str(e)}")
        
        # Update meeting status
        if sent_count > 0:
            self.meeting.invites_sent_date = timezone.now()
            if self.meeting.status == 'SCHEDULED':
                self.meeting.status = 'INVITES_SENT'
            self.meeting.save(update_fields=['invites_sent_date', 'status'])
        
        return {
            'sent': sent_count,
            'failed': failed_count,
            'errors': errors,
            'ics_generated': include_ics,
            'zoom_created': bool(self.meeting.meeting_link) if include_zoom else False,
        }
    
    def send_reminder(self) -> Dict[str, Any]:
        """
        Send a reminder to all invited members.
        """
        from corporate.models import MeetingAttendance
        
        # Get recipients who were invited
        tc_attendance_records = self.meeting.tc_attendance_records.select_related(
            'member', 'member__contact'
        ).filter(
            invite_sent=True,
            member__receives_meeting_invites=True,
            status__in=['INVITED', 'CONFIRMED']
        )
        
        sent_count = 0
        failed_count = 0
        errors = []
        
        for attendance in tc_attendance_records:
            member = attendance.member
            email = member.display_email
            
            if not email:
                continue
            
            subject = f"Reminder: {self.meeting.title} - {self.meeting.scheduled_date.strftime('%d %B %Y')}"
            
            context = {
                'meeting': self.meeting,
                'member': member,
                'client': self.meeting.committee.client,
                'is_reminder': True,
            }
            
            text_content = render_to_string('corporate/emails/meeting_reminder.txt', context)
            html_content = render_to_string('corporate/emails/meeting_reminder.html', context)
            
            try:
                email_message = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_message.attach_alternative(html_content, 'text/html')
                email_message.send(fail_silently=False)
                
                sent_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to send reminder to {email}: {str(e)}")
        
        # Update meeting
        if sent_count > 0:
            self.meeting.reminder_sent_date = timezone.now()
            self.meeting.save(update_fields=['reminder_sent_date'])
        
        return {
            'sent': sent_count,
            'failed': failed_count,
            'errors': errors,
        }
    
    def send_cancellation(self, reason: str = '') -> Dict[str, Any]:
        """
        Send cancellation notice to all invited members.
        """
        # Generate cancellation ICS
        ics_content = self.ics_generator.generate_cancellation()
        
        # Get recipients
        tc_attendance_records = self.meeting.tc_attendance_records.select_related(
            'member', 'member__contact'
        ).filter(invite_sent=True)
        
        sent_count = 0
        failed_count = 0
        errors = []
        
        for attendance in tc_attendance_records:
            member = attendance.member
            email = member.display_email
            
            if not email:
                continue
            
            subject = f"CANCELLED: {self.meeting.title} - {self.meeting.scheduled_date.strftime('%d %B %Y')}"
            
            context = {
                'meeting': self.meeting,
                'member': member,
                'reason': reason,
            }
            
            text_content = render_to_string('corporate/emails/meeting_cancellation.txt', context)
            html_content = render_to_string('corporate/emails/meeting_cancellation.html', context)
            
            try:
                email_message = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_message.attach_alternative(html_content, 'text/html')
                email_message.attach(
                    'cancellation.ics',
                    ics_content,
                    'text/calendar; method=CANCEL'
                )
                email_message.send(fail_silently=False)
                
                sent_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to send cancellation to {email}: {str(e)}")
        
        # Delete Zoom meeting if exists
        if self.meeting.meeting_id and self.zoom.is_configured:
            self.zoom.delete_meeting(self.meeting.meeting_id)
        
        # Update meeting status
        self.meeting.status = 'CANCELLED'
        self.meeting.save(update_fields=['status'])
        
        return {
            'sent': sent_count,
            'failed': failed_count,
            'errors': errors,
        }


def generate_meeting_ics(meeting) -> str:
    """
    Convenience function to generate ICS content for a meeting.
    """
    generator = ICSGenerator(meeting)
    return generator.generate()


def send_meeting_invites(meeting, include_zoom: bool = True) -> Dict[str, Any]:
    """
    Convenience function to send meeting invites.
    """
    service = MeetingInviteService(meeting)
    return service.send_invites(include_zoom=include_zoom)


def create_zoom_for_meeting(meeting) -> bool:
    """
    Convenience function to create a Zoom meeting.
    """
    service = MeetingInviteService(meeting)
    return service.create_zoom_meeting()
