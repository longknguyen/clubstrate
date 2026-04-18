from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect

from discussions.models import Comment, Post
from .models import CIO, Membership, JoinRequest

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

    if request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user, cio=cio).first()
        if membership is not None:
            role = membership.role

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
        'cios/cio_detail.html',
        {
            'cio': cio,
            'role': role,
            'posts': posts
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