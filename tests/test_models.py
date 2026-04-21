"""Basic tests for WebFace models"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TestingConfig
from models import db, User, Generation, GenerationType


@pytest.fixture
def app():
    """Create test app"""
    from flask import Flask
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    db.init_app(app)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    from flask import Flask
    from flask import Flask
    
    @app.route('/test')
    def test():
        return 'OK'
    
    app.test_client()


def test_user_model(app):
    """Test User model creation"""
    with app.app_context():
        db.create_all()
        
        user = User(
            username='testuser',
            email='test@test.com',
            password_hash='hash'
        )
        db.session.add(user)
        db.session.commit()
        
        assert user.id is not None
        assert user.username == 'testuser'
        assert user.is_admin == False


def test_generation_type_model(app):
    """Test GenerationType model"""
    with app.app_context():
        db.create_all()
        
        gt = GenerationType(
            type_key='test_model',
            name='Test Model'
        )
        db.session.add(gt)
        db.session.commit()
        
        assert gt.id is not None
        assert gt.enabled == True


def test_user_to_dict(app):
    """Test User to_dict"""
    with app.app_context():
        db.create_all()
        
        user = User(
            username='testuser',
            email='test@test.com',
            password_hash='hash'
        )
        db.session.add(user)
        db.session.commit()
        
        d = user.to_dict()
        assert d['username'] == 'testuser'
        assert d['email'] == 'test@test.com'