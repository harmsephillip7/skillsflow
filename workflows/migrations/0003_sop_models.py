# Generated manually - SOP module transformation
# This migration matches the database state after transformation

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workflows', '0002_business_process_flow'),
    ]

    operations = [
        # Step 1: Create new SOP models
        migrations.CreateModel(
            name='SOPCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('name', models.CharField(max_length=100)),
                ('code', models.SlugField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('icon', models.CharField(blank=True, default='folder', max_length=50)),
                ('color', models.CharField(blank=True, default='gray', max_length=20)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'SOP Category',
                'verbose_name_plural': 'SOP Categories',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SOP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('name', models.CharField(max_length=200)),
                ('code', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('purpose', models.TextField(blank=True, help_text='Why this SOP exists')),
                ('owner', models.CharField(blank=True, help_text='Department or role responsible', max_length=100)),
                ('version', models.CharField(default='1.0', max_length=20)),
                ('effective_date', models.DateField(blank=True, null=True)),
                ('is_published', models.BooleanField(default=False)),
                ('icon', models.CharField(blank=True, default='document-text', max_length=50)),
                ('estimated_duration', models.CharField(blank=True, help_text='e.g., 30 minutes, 2 hours', max_length=50)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sops', to='workflows.sopcategory')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'SOP',
                'verbose_name_plural': 'SOPs',
                'ordering': ['category__sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SOPStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('app_url_name', models.CharField(blank=True, help_text='Django URL name to link to (e.g., core:registration-list)', max_length=200)),
                ('app_url_label', models.CharField(blank=True, help_text='Button label for the link', max_length=100)),
                ('external_url', models.URLField(blank=True, help_text='External URL if not linking to app')),
                ('responsible_role', models.CharField(blank=True, help_text='Role responsible for this step', max_length=100)),
                ('tips', models.TextField(blank=True, help_text='Helpful tips for this step')),
                ('is_optional', models.BooleanField(default=False)),
                ('sop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='workflows.sop')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'SOP Step',
                'verbose_name_plural': 'SOP Steps',
                'ordering': ['sop', 'order'],
            },
        ),
        
        # Step 2: Remove workflow_instance FK from Task and add SOP fields
        migrations.RemoveField(
            model_name='task',
            name='workflow_instance',
        ),
        migrations.AddField(
            model_name='task',
            name='sop',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='workflows.sop'),
        ),
        migrations.AddField(
            model_name='task',
            name='sop_step',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='workflows.sopstep'),
        ),
        
        # Step 3: Delete old models (in reverse order of dependencies)
        migrations.DeleteModel(
            name='MilestoneCompletion',
        ),
        migrations.DeleteModel(
            name='WorkflowStageHistory',
        ),
        migrations.DeleteModel(
            name='WorkflowInstance',
        ),
        migrations.DeleteModel(
            name='WorkflowDefinition',
        ),
        migrations.DeleteModel(
            name='UserJourney',
        ),
        migrations.DeleteModel(
            name='Milestone',
        ),
    ]
