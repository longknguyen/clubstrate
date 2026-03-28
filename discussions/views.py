from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect

from cios.models import CIO, Membership
from discussions.models import Post, Comment


@login_required
def create_post(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if not Membership.objects.filter(user=request.user, cio=cio).exists():
        return redirect('cio_detail', cio_id=cio.id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content')
        image = request.FILES.get('image')

        Post.objects.create(
            cio=cio,
            author=request.user,
            title=title,
            content=content,
            image=image
        )

        return redirect('cio_detail', cio_id=cio.id)
    return render(request, 'discussions/create_post.html', {'cio': cio})

@login_required
def create_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)

    if request.method == 'POST':
        content = request.POST.get('content')
        image = request.FILES.get('image')
        parent_id = request.POST.get('parent_id')

        parent = None
        if parent_id:
            parent = Comment.objects.get(id=parent_id)

        Comment.objects.create(
            post=post,
            author=request.user,
            content=content,
            image=image,
            parent=parent
        )

    return redirect('cio_detail', cio_id=post.cio.id)

@login_required
def toggle_post_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)

    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)

    return redirect('cio_detail', cio_id=post.cio.id)

@login_required
def toggle_comment_like(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)

    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
    else:
        comment.likes.add(request.user)

    return redirect('cio_detail', cio_id=comment.post.cio.id)