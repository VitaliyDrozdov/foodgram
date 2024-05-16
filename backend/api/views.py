from django.contrib.auth import get_user_model

from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewset
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST


from api.filters import IngredientFilter, RecipeFilter
from api.pagination import LimitPagination
from api.permissions import IsAuthorAdminOrReadOnly
from api.serializers import (
    AvatarSerializer,
    CustomUserProfileSerializer,
    FavoritesSerializer,
    IngredientSerializer,
    RecipeCreateUpdateDeleteSerializer,
    RecipeIngredient,
    RecipeSerializer,
    ShoppingCartSerializer,
    ShortLinkSerializer,
    SubscribeSerializer,
    TagSerializer,
)
from recipe.models import Ingredient, Link, Recipe, Tag
from users.models import Subscription

User = get_user_model()


class UserViewSet(DjoserUserViewset):
    queryset = User.objects.all()
    serializer_class = CustomUserProfileSerializer
    pagination_class = LimitPagination

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="subscribe",
        permission_classes=(IsAuthenticated,),
    )
    def subscribe(self, request, **kwargs):
        user = request.user
        following = get_object_or_404(User, id=self.kwargs.get("id"))
        if request.method == "POST":
            serializer = SubscribeSerializer(
                following, data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            Subscription.objects.create(user=user, following=following)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            cur_sub = Subscription.objects.filter(following=following, user=user)
            if not cur_sub.exists():
                return Response(status=HTTP_400_BAD_REQUEST)
            cur_sub.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["get"],
        url_path="subscriptions",
        permission_classes=(IsAuthenticated,),
    )
    def subscriptions(self, request):
        user = request.user
        subscriptions = User.objects.filter(following__user=user)
        if subscriptions:
            pages = self.paginate_queryset(subscriptions)
            serializer = SubscribeSerializer(
                pages, many=True, context={"request": request}
            )
            # serializer.is_valid(raise_exception=True)
            return self.get_paginated_response(serializer.data)
        else:
            return Response("Подписки отсутствуют", status=HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], permission_classes=(IsAuthenticated,))
    def me(self, request, *args, **kwargs):
        return super().me(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["put", "patch", "delete"],
        url_path="me/avatar",
        permission_classes=(IsAuthenticated,),
    )
    def set_avatar(self, request):
        if request.method == "PUT" or request.method == "PATCH":
            serializer = AvatarSerializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        elif request.method == "DELETE":
            request.user.avatar.delete(save=True)
            request.user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientListDetailViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngredientSerializer
    queryset = Ingredient.objects.all()
    filter_backends = (IngredientFilter,)
    search_fields = ("^name",)
    permission_classes = (AllowAny,)
    pagination_class = None


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()


class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeSerializer
    queryset = Recipe.objects.all()
    pagination_class = LimitPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    permission_classes = (IsAuthorAdminOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeSerializer
        return RecipeCreateUpdateDeleteSerializer

    @action(detail=True, methods=["post", "delete"], url_path="favorite")
    def favorite(self, request, pk: int):
        try:
            recipe = get_object_or_404(Recipe, id=pk)
        except Http404:
            return Response(status=HTTP_400_BAD_REQUEST)
        if request.method == "POST":
            serializer = FavoritesSerializer(
                data={"user": request.user.id, "recipe": recipe.id},
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            cur_recipe = request.user.favorites.filter(recipe=recipe, user=request.user)
            if not cur_recipe.exists():
                return Response(status=HTTP_400_BAD_REQUEST)
            cur_recipe.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post", "delete"], url_path="shopping_cart")
    def shopping_cart(self, request, pk: int):
        recipe = get_object_or_404(Recipe, id=pk)
        # try:
        #     recipe = get_object_or_404(Recipe, id=pk)
        # except Http404:
        # return Response(status=HTTP_400_BAD_REQUEST)
        if request.method == "POST":
            serializer = ShoppingCartSerializer(
                data={"user": request.user.id, "recipe": recipe.id},
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            cur_recipe = request.user.shopping_cart.filter(
                recipe=recipe, user=request.user
            )
            if not cur_recipe.exists():
                return Response(status=HTTP_400_BAD_REQUEST)
            cur_recipe.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="download_shopping_cart")
    def download_shopping_cart(self, request):
        user = request.user
        ingredients = (
            RecipeIngredient.objects.filter(recipe__shopping_cart__user=user)
            .values("ingredient__name", "ingredient__measurement_unit")
            .annotate(amount=Sum("amount"))
        )
        shopping_list = "Список покупок\n"
        for ingredient in ingredients:
            shopping_list += "".join(
                f'- {ingredient["ingredient__name"]} '
                f'({ingredient["ingredient__measurement_unit"]})'
                f' - {ingredient["amount"]}\n'
            )
        filename = f"{user.username}_shopping_list.txt"
        response = HttpResponse(shopping_list, content_type="text/plain")
        response["Content-Disposition"] = f"attachment; filename={filename}.txt"
        return response

    @action(detail=True, methods=["get"], url_path="get-link")
    def get_short_link(self, request, pk: int):
        # recipe_url = request.build_absolute_uri(f"/recipes/{pk}/")
        serializer = ShortLinkSerializer(data={"pk": pk}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def redirect_to_recipe(request, short_code):
    link = get_object_or_404(Link, short_code=short_code)
    # serializer = ShortLinkSerializer(
    #     data={"short_link": link.short_link}, context={"request": request}
    # )
    # return Response(serializer.data)
    return redirect(link.original_link)
