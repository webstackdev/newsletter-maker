from django.db.models import Avg

from .models import TenantConfig


def dashboard_callback(request, context):
    # Calculate the average authority weight across all tenants
    avg_weight = TenantConfig.objects.aggregate(Avg('upvote_authority_weight'))['upvote_authority_weight__avg']

    # Add it to the template context
    context.update({
        "avg_authority_weight": round(avg_weight, 2) if avg_weight else 0,
    })
    return context
