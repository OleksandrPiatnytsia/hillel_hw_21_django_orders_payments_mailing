from .cart import Cart


def cart(request):
    """Adds "cart" to the context of every template rendered with a request.

    Registered in settings.TEMPLATES["OPTIONS"]["context_processors"].
    The navbar uses {{ cart|length }}: Cart.__len__ reads only the session,
    so the counter costs no SQL query. The book list is loaded from the
    database only when a template iterates the cart (the cart page).
    """
    return {"cart": Cart(request)}
