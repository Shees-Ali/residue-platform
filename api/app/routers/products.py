import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_factory, require_role
from app.auth.owners import factory_of
from app.db_models.tables import Factory, Product
from app.deps import DbSession
from app.models.market import ProductIn, ProductOut, ProductPatch

router = APIRouter(prefix="/api/products", tags=["products"])
as_shopper = Depends(require_role("buyer", "factory", "admin"))


def _out(product: Product, factory_name: str) -> ProductOut:
    return ProductOut(
        id=str(product.id),
        factory_id=str(product.factory_id),
        factory_name=factory_name,
        name=product.name,
        unit_price=product.unit_price,
        stock=product.stock,
        active=product.active,
    )


@router.get("", response_model=list[ProductOut])
async def get_products_root(db: DbSession, user: AuthUser = as_shopper):
    """The marketplace: buyers and admins see what is for sale, a factory sees all of its own."""
    query = select(Product, Factory.name).join(Factory, Factory.id == Product.factory_id)
    if user.role == "factory":
        query = query.where(Product.factory_id == (await factory_of(db, user)).id)
    else:
        query = query.where(Product.active, Product.stock > 0)
    rows = (await db.execute(query.order_by(Product.name))).all()
    return [_out(p, name) for p, name in rows]


@router.post("", response_model=ProductOut, status_code=201)
async def post_products_root(db: DbSession, body: ProductIn, user: AuthUser = as_factory):
    factory = await factory_of(db, user)
    product = Product(
        factory_id=factory.id, name=body.name, unit_price=body.unit_price, stock=body.stock
    )
    db.add(product)
    await db.flush()
    out = _out(product, factory.name)
    await db.commit()
    return out


@router.patch("/{product_id}", response_model=ProductOut)
async def patch_product(
    db: DbSession, product_id: str, body: ProductPatch, user: AuthUser = as_factory
):
    factory = await factory_of(db, user)
    try:
        key = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(404, "Unknown product") from None
    product = (
        await db.execute(
            select(Product).where(Product.id == key, Product.factory_id == factory.id)
        )
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(404, "Unknown product")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.flush()
    out = _out(product, factory.name)
    await db.commit()
    return out
