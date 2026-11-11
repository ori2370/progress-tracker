from django import forms

from .models import WorkoutRoutine, WorkoutTemplate, TemplateExercise, ExerciseDefinition

class WorkoutRoutineForm(forms.ModelForm):
    class Meta:
        model = WorkoutRoutine
        fields = ["name", "sessions_per_week", "notes"]
        labels = {
            "name": "Routine name",
            "sessions_per_week": "Sessions per week",
        }
        widgets = {
            "sessions_per_week": forms.NumberInput(
                attrs={"min": 1, "max": 7}
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

class WorkoutTemplateForm(forms.ModelForm):
    class Meta:
        model = WorkoutTemplate
        fields = ["name", "notes"]
        labels = {
            "name": "Workout name",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, routine, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.routine = routine

class TemplateExerciseForm(forms.ModelForm):
    class Meta:
        model = TemplateExercise
        fields = ["definition", "position", "planned_sets", "target_reps"]
        labels = {
            "definition": "Exercise",
            "position": "Order in workout",
            "planned_sets": "Sets",
            "target_reps": "Target reps",
        }
        widgets = {
            "position": forms.NumberInput(attrs={"min": 1}),
            "planned_sets": forms.NumberInput(attrs={"min": 1}),
            "target_reps": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, template, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.template = template
        self.fields["definition"].queryset = (
            ExerciseDefinition.objects.filter(user=user)
        )