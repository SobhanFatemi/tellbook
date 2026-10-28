from .homepage import HomepageBooks, HomepageSelection
from .admin_api import AdminBookList, AdminBookDetail, AdminEditionCreate
from .posts import PublicPostList, AdminPostList, AdminPostDetail
from django.urls import path

from .views import BookDetailView, BookSearchFilterOptionsView, BookSearchView, BookSuggestView, BookUpdateView, FeaturedBookListView

urlpatterns = [
    path("homepage/", HomepageBooks.as_view()),
    path("admin/homepage/", HomepageSelection.as_view()),
    path("admin/books/", AdminBookList.as_view()),
    path("admin/books/<int:pk>/", AdminBookDetail.as_view()),
    path("admin/editions/", AdminEditionCreate.as_view()),
    path("posts/", PublicPostList.as_view()),
    path("admin/posts/", AdminPostList.as_view()),
    path("admin/posts/<int:pk>/", AdminPostDetail.as_view()),
    path("search/", BookSearchView.as_view(), name="book-search"),
    path("search/filters/", BookSearchFilterOptionsView.as_view(), name="book-search-filters"),
    path("suggest/", BookSuggestView.as_view(), name="book-suggest"),
    path("<int:pk>/", BookDetailView.as_view(), name="book-detail"),
    path("<int:pk>/edit/", BookUpdateView.as_view(), name="book-update"),
    path("featured/", FeaturedBookListView.as_view(), name="featured-books"),
]
