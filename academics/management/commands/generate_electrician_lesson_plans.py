"""
Generate Lesson Plans for QCTO Electrician Qualification

Creates detailed lesson plan templates for all Knowledge and Practical modules,
and outcome checklists for Workplace modules.

Usage: python manage.py generate_electrician_lesson_plans
"""

from django.core.management.base import BaseCommand
from academics.models import Module, LessonPlanTemplate


MODULE_CONTENT = {
    # KNOWLEDGE MODULES
    "337935": {
        "topics": ["Electrical Theory & Safety", "Ohm's Law", "Series Circuits", "Parallel Circuits", "Kirchhoff's Laws", "AC Theory", "Three-Phase Systems", "Transformers", "Motors Overview"],
        "outcomes": ["Apply Ohm's Law to calculate voltage, current, and resistance", "Analyze series and parallel circuits", "Understand AC and three-phase power"],
        "equipment": ["Multimeter", "Oscilloscope", "Power supply", "Resistors", "Capacitors"],
        "safety": ["Electrical shock hazards", "Capacitor discharge procedures", "Proper use of test equipment"]
    },
    "337936": {
        "topics": ["Drawing Standards", "Electrical Symbols (SANS/IEC)", "Single-Line Diagrams", "Wiring Diagrams", "Circuit Schematics", "Cable Schedules"],
        "outcomes": ["Interpret standard electrical symbols", "Read and understand single-line diagrams", "Create basic wiring diagrams"],
        "equipment": ["Drawing instruments", "Templates", "CAD software"],
        "safety": ["Proper ergonomics", "Eye strain prevention"]
    },
    "337937": {
        "topics": ["DC Motor Construction", "DC Motor Types", "Single-Phase AC Motors", "Three-Phase Induction Motors", "Motor Starting Methods", "Motor Protection", "VSDs"],
        "outcomes": ["Explain DC motor operating principles", "Identify motor types by construction", "Select appropriate starting methods"],
        "equipment": ["Various motor types", "Starters", "VSD", "Insulation tester"],
        "safety": ["Rotating machinery hazards", "High voltage precautions", "Lockout procedures"]
    },
    "337938": {
        "topics": ["Control Systems Basics", "Contactors and Relays", "Motor Control Circuits", "Sensors and Transducers", "PLC Introduction", "PLC Programming", "HMI"],
        "outcomes": ["Design basic motor control circuits", "Select appropriate control devices", "Understand PLC operation principles"],
        "equipment": ["PLC trainer", "Contactors", "Sensors", "Push buttons", "Pilot lights"],
        "safety": ["Control circuit isolation", "Emergency stop requirements", "Testing procedures"]
    },
    "337939": {
        "topics": ["SANS 10142 Introduction", "Protection Against Shock", "Overcurrent Protection", "Earthing and Bonding", "Wiring Systems", "Inspection and Testing", "CoC Requirements"],
        "outcomes": ["Apply SANS 10142 requirements correctly", "Determine appropriate protection measures", "Understand CoC requirements"],
        "equipment": ["SANS 10142 code", "Testing instruments"],
        "safety": ["Live testing precautions", "Permit to work systems", "PPE requirements"]
    },
    "337940": {
        "topics": ["Semiconductor Fundamentals", "Diodes", "Transistors", "Power Electronics", "Rectifier Circuits", "Voltage Regulators", "Op-Amps"],
        "outcomes": ["Explain semiconductor operation", "Analyze rectifier circuits", "Understand basic power electronics"],
        "equipment": ["Electronic components", "Breadboard", "Oscilloscope", "Function generator"],
        "safety": ["Static sensitive device handling", "Soldering safety", "Component ratings"]
    },
    "337941": {
        "topics": ["Fault Finding Methodology", "Test Equipment", "Continuity Testing", "Insulation Testing", "Earth Fault Location", "Motor Fault Diagnosis"],
        "outcomes": ["Apply systematic fault finding approach", "Use test equipment correctly", "Locate common electrical faults"],
        "equipment": ["Multimeter", "Insulation tester", "Earth resistance tester", "Clamp meter"],
        "safety": ["Live testing procedures", "Isolation verification", "Test equipment safety"]
    },
    "337942": {
        "topics": ["Electrical Contracting", "Quotations and Tenders", "Project Management", "Labour Relations", "Quality Management", "Professional Ethics"],
        "outcomes": ["Prepare basic electrical quotations", "Understand project management principles", "Demonstrate professional conduct"],
        "equipment": ["Sample contracts", "Estimation software", "Standards documents"],
        "safety": ["Document security", "Professional liability"]
    },
    # PRACTICAL MODULES
    "337943": {
        "topics": ["Surface Wiring", "Conduit Installation", "Trunking Systems", "Cable Tray", "Cable Selection", "Termination Techniques", "Testing"],
        "outcomes": ["Install various wiring systems correctly", "Select appropriate cable types and sizes", "Terminate cables professionally"],
        "equipment": ["Conduit bender", "Cable cutters", "Crimping tools", "Testing instruments"],
        "safety": ["Working at heights", "Manual handling", "Sharp edges", "Dust control"]
    },
    "337944": {
        "topics": ["Lighting Circuit Design", "Switch Types", "Socket Outlet Circuits", "Distribution Boards", "Metering", "Emergency Lighting"],
        "outcomes": ["Install lighting circuits correctly", "Install socket outlet circuits", "Select appropriate protection devices"],
        "equipment": ["Installation tools", "Distribution boards", "MCBs", "RCDs", "Lighting fixtures"],
        "safety": ["Working live precautions", "Working at heights", "Dust and debris"]
    },
    "337945": {
        "topics": ["Switchgear Installation", "Motor Installation", "Starter Installation", "Control Panels", "Equipment Earthing", "Commissioning"],
        "outcomes": ["Install electrical equipment safely", "Commission electrical installations", "Complete installation documentation"],
        "equipment": ["Installation tools", "Lifting equipment", "Testing instruments", "PPE"],
        "safety": ["Heavy equipment handling", "Electrical hazards", "Confined spaces"]
    },
    "337946": {
        "topics": ["Motor Connections", "Rotation Verification", "Motor Testing", "Vibration Analysis", "Insulation Testing", "Load Testing", "Commissioning"],
        "outcomes": ["Connect motors correctly", "Verify motor operation", "Perform motor testing"],
        "equipment": ["Motor analyzer", "Phase rotation meter", "Insulation tester", "Clamp meter"],
        "safety": ["Rotating machinery", "High voltage", "Noise exposure"]
    },
    "337947": {
        "topics": ["Control Panel Wiring", "Component Installation", "Wiring Standards", "Ferrule Systems", "Point-to-Point Testing", "Functional Testing"],
        "outcomes": ["Wire control panels professionally", "Test control circuits systematically", "Document wiring installations"],
        "equipment": ["Wiring tools", "Ferrule crimper", "Labeling machine", "Test instruments"],
        "safety": ["Control voltage hazards", "Sharp wire ends", "Confined panel spaces"]
    },
    "337948": {
        "topics": ["PLC Hardware Config", "I/O Wiring", "Ladder Logic", "Timer/Counter Programming", "Program Testing", "Online Monitoring", "Backup"],
        "outcomes": ["Configure PLC hardware", "Write basic PLC programs", "Test and commission PLC systems"],
        "equipment": ["PLC hardware", "Programming software", "Laptop", "I/O simulators"],
        "safety": ["Program testing safety", "Machine guarding", "Emergency stops"]
    },
    "337949": {
        "topics": ["Preventive Maintenance", "Inspection Procedures", "Cleaning/Servicing", "Component Replacement", "Thermal Imaging", "Vibration Monitoring"],
        "outcomes": ["Implement preventive maintenance", "Perform routine inspections", "Replace components correctly"],
        "equipment": ["Maintenance tools", "Thermal camera", "Vibration analyzer", "PPE"],
        "safety": ["Isolation procedures", "Working live safely", "Chemical handling"]
    },
    "337950": {
        "topics": ["Fault Diagnosis", "Component Testing", "Repair Techniques", "Motor Rewinding", "Contactor Repair", "Testing After Repair"],
        "outcomes": ["Diagnose electrical faults", "Repair electrical components", "Test repaired equipment"],
        "equipment": ["Repair tools", "Soldering equipment", "Test instruments", "Spare parts"],
        "safety": ["Component handling", "Soldering hazards", "Testing safety"]
    },
    # WORKPLACE MODULES
    "337951": {"outcomes": ["Install surface and conduit wiring in workplace", "Apply workplace safety procedures", "Work as part of installation team", "Complete to workplace quality standards"]},
    "337952": {"outcomes": ["Install power circuits in commercial/industrial settings", "Install lighting systems to specification", "Work with distribution boards", "Apply circuit testing procedures"]},
    "337953": {"outcomes": ["Install electrical equipment under supervision", "Connect motors and starters", "Participate in commissioning", "Apply workplace H&S requirements"]},
    "337954": {"outcomes": ["Wire control panels in industrial environment", "Assist with PLC installations", "Participate in control system commissioning", "Apply control system safety"]},
    "337955": {"outcomes": ["Perform preventive maintenance tasks", "Participate in maintenance shutdowns", "Use condition monitoring equipment", "Complete maintenance records"]},
    "337956": {"outcomes": ["Diagnose faults under supervision", "Participate in electrical repairs", "Apply systematic fault finding", "Document fault finding and repair"]},
}


class Command(BaseCommand):
    help = 'Generate lesson plans for QCTO Electrician qualification modules'

    def handle(self, *args, **options):
        modules = Module.objects.filter(
            qualification__saqa_id='91761'
        ).order_by('sequence_order')
        
        if not modules.exists():
            self.stdout.write(self.style.ERROR(
                'Electrician modules not found. Run import_qcto_electrician first.'
            ))
            return
        
        self.stdout.write(f'Found {modules.count()} modules for Electrician qualification')
        
        total_lesson_plans = 0
        total_checklists = 0
        
        for module in modules:
            content = MODULE_CONTENT.get(module.code, {})
            
            if not content:
                self.stdout.write(self.style.WARNING(
                    f'  No content defined for {module.code}: {module.title}'
                ))
                continue
            
            # Calculate number of sessions (6 hours per session)
            notional_hours = module.credits * 10
            num_sessions = notional_hours // 6
            
            if module.module_type == 'W':
                self._create_workplace_checklist(module, content)
                total_checklists += 1
            else:
                created = self._create_lesson_plans(module, content, num_sessions)
                total_lesson_plans += created
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Lesson plans created: {total_lesson_plans}'))
        self.stdout.write(self.style.SUCCESS(f'Workplace checklists created: {total_checklists}'))
        self.stdout.write(self.style.SUCCESS('Generation complete!'))
    
    def _create_lesson_plans(self, module, content, num_sessions):
        """Create detailed lesson plans for K/P modules"""
        self.stdout.write(f'\n{module.code}: {module.title} ({num_sessions} sessions)')
        
        topics = content.get('topics', [])
        outcomes = content.get('outcomes', [])
        equipment = content.get('equipment', [])
        safety = content.get('safety', [])
        
        created_count = 0
        
        for session_num in range(1, num_sessions + 1):
            # Cycle through topics
            topic_index = (session_num - 1) % len(topics) if topics else 0
            topic_title = topics[topic_index] if topics else f'Session {session_num}'
            
            # Build classroom topics structure as list
            classroom_topics = [
                {
                    "title": "Introduction",
                    "duration_minutes": 25,
                    "content": f"Review of previous session. Introduction to {topic_title}.",
                    "key_points": [f"Key concept from {topic_title}"]
                },
                {
                    "title": topic_title,
                    "duration_minutes": 55,
                    "content": f"Detailed exploration of {topic_title}.",
                    "key_points": [outcomes[topic_index % len(outcomes)]] if outcomes else []
                },
                {
                    "title": "Application",
                    "duration_minutes": 30,
                    "content": f"Worked examples and calculations for {topic_title}.",
                    "key_points": []
                }
            ]
            
            # Build practical activities as list
            if module.module_type == 'P':
                practical_activities = [
                    {
                        "title": f"Demonstration: {topic_title}",
                        "duration_minutes": 45,
                        "description": f"Instructor demonstrates {topic_title} techniques.",
                        "steps": ["Observe safety procedures", "Watch demonstration", "Ask questions"],
                        "equipment": equipment[:3] if equipment else [],
                        "assessment_criteria": [f"Understanding of {topic_title} demonstration"]
                    },
                    {
                        "title": "Guided Practice",
                        "duration_minutes": 90,
                        "description": f"Learners practice {topic_title} under supervision.",
                        "steps": ["Follow instructor guidance", "Practice technique", "Seek feedback"],
                        "equipment": equipment if equipment else [],
                        "assessment_criteria": [f"Correct application of {topic_title} techniques"]
                    },
                    {
                        "title": "Independent Practice",
                        "duration_minutes": 75,
                        "description": f"Independent application of {topic_title} skills.",
                        "steps": ["Work independently", "Apply learned skills", "Self-check work"],
                        "equipment": equipment if equipment else [],
                        "assessment_criteria": [f"Independent completion of {topic_title} tasks"]
                    },
                    {
                        "title": "Debrief",
                        "duration_minutes": 30,
                        "description": "Review of practical work, feedback, and cleanup.",
                        "steps": ["Review completed work", "Receive feedback", "Clean up workspace"],
                        "equipment": [],
                        "assessment_criteria": []
                    }
                ]
            else:
                # Knowledge modules have lighter practical
                practical_activities = [
                    {
                        "title": "Demonstration",
                        "duration_minutes": 30,
                        "description": f"Demonstration related to {topic_title}.",
                        "steps": ["Watch demonstration", "Take notes"],
                        "equipment": equipment[:2] if equipment else [],
                        "assessment_criteria": []
                    },
                    {
                        "title": "Exercises",
                        "duration_minutes": 120,
                        "description": f"Exercises and calculations on {topic_title}.",
                        "steps": ["Complete exercises", "Check answers", "Review mistakes"],
                        "equipment": ["Calculator", "Reference materials"],
                        "assessment_criteria": [f"Correct completion of {topic_title} exercises"]
                    },
                    {
                        "title": "Review",
                        "duration_minutes": 60,
                        "description": "Review and discussion of exercises.",
                        "steps": ["Discuss solutions", "Clarify misunderstandings"],
                        "equipment": [],
                        "assessment_criteria": []
                    },
                    {
                        "title": "Assessment Prep",
                        "duration_minutes": 30,
                        "description": "Formative assessment preparation.",
                        "steps": ["Review key concepts", "Practice questions"],
                        "equipment": [],
                        "assessment_criteria": []
                    }
                ]
            
            # Create the lesson plan with correct field names
            lesson_plan, created = LessonPlanTemplate.objects.update_or_create(
                module=module,
                session_number=session_num,
                defaults={
                    'topic': topic_title,
                    'classroom_duration_minutes': 120,
                    'practical_duration_minutes': 240,
                    'classroom_introduction': f'Welcome and review. Today we cover {topic_title}.',
                    'classroom_topics': classroom_topics,
                    'discussion_questions': [
                        f'What is the importance of {topic_title}?',
                        f'How does {topic_title} apply in real-world scenarios?'
                    ],
                    'key_concepts': [outcomes[topic_index % len(outcomes)]] if outcomes else [topic_title],
                    'classroom_summary': f'Summary of {topic_title}. Preview of next session.',
                    'practical_activities': practical_activities,
                    'safety_briefing': '. '.join(safety) if safety else 'Standard electrical safety procedures apply.',
                    'demonstration_notes': f'Demonstrate key aspects of {topic_title}.',
                    'practical_debrief': 'Review work completed, provide feedback, ensure cleanup.',
                    'learning_outcomes': [outcomes[topic_index % len(outcomes)]] if outcomes else [f'Understand {topic_title}'],
                    'equipment_list': [{"type": "equipment", "name": e, "quantity": 1} for e in equipment] if equipment else [],
                    'consumables_list': [
                        {"type": "consumable", "name": "Cable ties", "quantity": 10},
                        {"type": "consumable", "name": "Electrical tape", "quantity": 1}
                    ],
                    'resources_required': [{"type": "handout", "name": f"{topic_title} handout", "quantity": 1}],
                    'assessment_criteria': [f'Demonstrate understanding of {topic_title}', 'Apply concepts correctly'],
                    'facilitator_notes': f'Ensure all learners understand {topic_title} before moving on.',
                    'preparation_checklist': ['Prepare materials', 'Test equipment', 'Review lesson content'],
                    'common_mistakes': [f'Common error when learning {topic_title}'],
                }
            )
            
            if created:
                created_count += 1
        
        self.stdout.write(f'  Created {created_count} lesson plans')
        return created_count
    
    def _create_workplace_checklist(self, module, content):
        """Create workplace outcome checklist"""
        self.stdout.write(f'\n{module.code}: {module.title} (Workplace)')
        
        outcomes = content.get('outcomes', [])
        
        # Create single entry that serves as outcome checklist
        checklist_activities = [
            {
                "title": "Workplace Outcome Verification",
                "duration_minutes": module.credits * 10 * 60,  # Total notional time in minutes
                "description": "Mentor-supervised workplace activities",
                "steps": outcomes,
                "equipment": ["As per workplace requirements"],
                "assessment_criteria": outcomes
            }
        ]
        
        lesson_plan, created = LessonPlanTemplate.objects.update_or_create(
            module=module,
            session_number=1,
            defaults={
                'topic': f'Workplace Outcomes: {module.title}',
                'classroom_duration_minutes': 0,
                'practical_duration_minutes': module.credits * 10 * 60,
                'classroom_introduction': '',
                'classroom_topics': [],
                'discussion_questions': [],
                'key_concepts': outcomes,
                'classroom_summary': '',
                'practical_activities': checklist_activities,
                'safety_briefing': 'Comply with all workplace health and safety requirements. Use required PPE at all times.',
                'demonstration_notes': 'Workplace mentor will demonstrate as required.',
                'practical_debrief': 'Review workplace evidence portfolio with mentor.',
                'learning_outcomes': outcomes,
                'equipment_list': [{"type": "equipment", "name": "As per workplace", "quantity": 1}],
                'consumables_list': [{"type": "consumable", "name": "As per workplace", "quantity": 1}],
                'resources_required': [
                    {"type": "handout", "name": "Learner logbook", "quantity": 1},
                    {"type": "digital", "name": "Evidence portfolio", "quantity": 1}
                ],
                'assessment_criteria': outcomes + ['Workplace mentor verification', 'Portfolio of evidence submission'],
                'facilitator_notes': 'Workplace mentor must verify each outcome.',
                'preparation_checklist': ['Review outcomes with learner', 'Plan workplace activities', 'Prepare evidence collection'],
                'common_mistakes': ['Incomplete evidence', 'Missing mentor signatures'],
            }
        )
        
        status = 'Created' if created else 'Updated'
        self.stdout.write(f'  {status} workplace checklist with {len(outcomes)} outcomes')
