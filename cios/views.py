from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect

from discussions.models import Comment
from .models import CIO, Membership
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
