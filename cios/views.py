from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect

from discussions.models import Comment, Post
from .models import CIO, Membership, JoinRequest, Event, Reminder

from django.http import JsonResponse
from django.utils import timezone


def landing(request):
    return render(request, 'cios/landing.html')

def home(request):
    cios = CIO.objects.all().order_by('name')
    return render(request, 'cios/home.html', {'cios': cios})

@login_required
def create_cio(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        if name:
            cio = CIO.objects.create(
                name=name,
                created_by=request.user,
            )

            Membership.objects.create(
                user=request.user,
                cio=cio,
                role='officer',
            )
            return redirect('home')
    return render(request, 'cios/create_cio.html')

def cio_detail(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    role = 'viewer'
    join_requests = []

    if request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user, cio=cio).first()
        if membership is not None:
            role = membership.role

    if role == 'officer':
        join_requests = JoinRequest.objects.filter(cio=cio, status='pending')

    posts = cio.posts.prefetch_related(
        'likes',
        Prefetch(
            'comments',
            queryset=Comment.objects.filter(parent__isnull=True)
            .select_related('author')
            .prefetch_related('likes', 'replies')
        )
    ).order_by('-created_at')

    return render(request,
                  'cios/cio_page.html',
                  {
            'cio': cio,
            'role': role,
            'posts': posts,
            'join_requests': join_requests
        },
                  )

@login_required
def edit_cio_about(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    membership = Membership.objects.filter(user=request.user, cio=cio).first()
    if not membership or membership.role != 'officer':
        return redirect(f'/{cio.id}/')

    if request.method == 'POST':
        cio.description = request.POST.get('description', '').strip()
        cio.dues = request.POST.get('dues', '').strip()
        cio.commitment_level = request.POST.get('commitment_level', '').strip()
        cio.time_expectations = request.POST.get('time_expectations', '').strip()

        if request.POST.get('remove_image'):
            cio.about_image = None

        image = request.FILES.get('about_image')
        if image:
            cio.about_image = image

        cio.save()
        return redirect(f'/{cio.id}/')
    return render(request, 'cios/edit_cio_about.html', {'cio': cio})

@login_required
def request_to_join(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if request.method == 'POST':
        membership = Membership.objects.filter(user=request.user, cio=cio).first()
        join_request = JoinRequest.objects.filter(user=request.user, cio=cio).first()

        if membership is None and join_request is None:
            JoinRequest.objects.create(
                user=request.user,
                cio=cio,
                status='pending'
            )

    return redirect(f'/{cio.id}/')

@login_required
def accept_request(request, request_id):
    join_request = get_object_or_404(JoinRequest, pk=request_id)

    if request.method == 'POST':
        membership = Membership.objects.filter(
            user=join_request.user,
            cio=join_request.cio
        ).first()

        if membership is None:
            Membership.objects.create(
                user=join_request.user,
                cio=join_request.cio,
                role='member'
            )

        join_request.status = 'approved'
        join_request.save()

    return redirect(f'/{join_request.cio.id}/')

@login_required
def cio_calendar(request, cio_id):
    cio = get_object_or_404(CIO, id=cio_id)
    membership = Membership.objects.filter(user=request.user, cio=cio).first()

    # creating event list for FullCalendar
    events = Event.objects.filter(cio=cio)
    events_data = [
        {
            "id": e.id,
            "title": e.title,
            "start": e.start_time.isoformat(),
            "description": e.description,
            "location": e.location,
        }
        for e in events
    ]

    # getting user reminders
    reminder_event_ids = set(
        Reminder.objects.filter(user=request.user, event__cio=cio)
        .values_list('event_id', flat=True)
    )

    return render(request, 'cios/calendar.html', {
        'cio': cio,
        'membership': membership,
        'is_officer': membership and membership.role == Membership.OFFICER,
        'events_json': json.dumps(events_data),
        'reminder_event_ids': list(reminder_event_ids),
    })

@login_required
def add_event(request, cio_id):
    cio = get_object_or_404(CIO, id=cio_id)
    membership = Membership.objects.filter(user=request.user, cio=cio, role=Membership.OFFICER).first()

    # only officers can add events
    if not membership:
        return JsonResponse({'error': 'Officers only'}, status=403)

    if request.method == 'POST':
        data = json.loads(request.body)
        event = Event.objects.create(
            cio=cio,
            title=data['title'],
            description=data.get('description', ''),
            start_time=data['start_time'],  # expects ISO string
            location=data.get('location', ''),
            created_by=request.user,
        )
        return JsonResponse({
            'id': event.id,
            'title': event.title,
            'start': event.start_time.isoformat(),
            'description': event.description,
            'location': event.location,
        })

    return JsonResponse({'error': 'POST required'}, status=405)

@login_required
def toggle_reminder(request, event_id): # creating a toggle for users to choose to have reminders for certain events
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        reminder, created = Reminder.objects.get_or_create(
            user=request.user,
            event=event,
            defaults={'remind_at': event.start_time}  # default: remind at event time
        )
        if not created:
            reminder.delete()
            return JsonResponse({'status': 'removed'})
        return JsonResponse({'status': 'added'})

    return JsonResponse({'error': 'POST required'}, status=405)