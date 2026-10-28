"""Endpoints that need a signed-in user (FR-0.2)."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..auth import require_user
from ..controllers.user_controllers import AlertController, FavouriteController, UserProfileController, VisitController
from ..db import get_db
from ..geo import today_sg
from ..models import User
from ..schemas import AlertOut, FavouriteIn, FavouriteOut, MeOut, ProfileIn, ProfileOut, VisitIn, VisitOut

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=MeOut)
def me(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, has_profile=UserProfileController.get(db, user) is not None)


@router.get("/profile", response_model=ProfileOut | None)
def get_profile(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return UserProfileController.get(db, user)


@router.put("/profile", response_model=ProfileOut)
def save_profile(data: ProfileIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return UserProfileController.save(db, user, data)


@router.get("/favourites", response_model=list[FavouriteOut])
def favourites(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return FavouriteController.list(db, user, today_sg())


@router.post("/favourites", response_model=FavouriteOut, status_code=201)
def add_favourite(data: FavouriteIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return FavouriteController.add(db, user, data, today_sg())


@router.delete("/favourites/{fav_id}", status_code=204)
def remove_favourite(fav_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    FavouriteController.remove(db, user, fav_id)
    return Response(status_code=204)


@router.get("/visits", response_model=list[VisitOut])
def visits(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return VisitController.list(db, user)


@router.post("/visits", response_model=VisitOut, status_code=201)
def add_visit(data: VisitIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return VisitController.add(db, user, data, today_sg())


@router.get("/alerts", response_model=list[AlertOut])
def alerts(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return AlertController.list(db, user, today_sg())


@router.post("/alerts/{alert_id}/read", status_code=204)
def read_alert(alert_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    AlertController.mark_read(db, user, alert_id)
    return Response(status_code=204)
