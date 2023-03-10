from flask import render_template, url_for, flash, redirect, request
from sqlalchemy import text
from datetime import date
from books.forms import LoginForm, RegistrationForm, SearchBarForm, OrderForm, PromoteUserForm, StockLevelForm, AddBookForm,TopNRatingsForm, TrustForm, RateForm
from books import app, bcrypt
from books.models import *
from flask_login import login_user, current_user, login_required, logout_user


@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    s_form = SearchBarForm()
    books = []
    
    #Select all books
    # Query for search
    query= f"""
        SELECT * FROM book LIMIT 100     
        """     
    query = text(query)
    q = db.session.execute(query)

    for row in q:
        books.append(Book.query.filter_by(ISBN=row[0]).first())
        print(row)       
    # Validate for search form
    if s_form.validate_on_submit():
        order = ""
        sub = ""

        # Query for search
        query_txt = f"""
            SELECT DISTINCT b.ISBN 
            FROM book b {sub}, authors aut, author a
            WHERE 
                b.ISBN = aut.ISBN AND a.authorID = aut.authorID OR 
                ((a.fname || ' ' || a.lname) LIKE '%{s_form.author_field.data}%')'  
                 {order} 
                LIMIT 100     
        """        
        # Execute query and add data to list to send to HTML
        query_txt = text(query_txt)
        q = db.session.execute(query_txt)

        for row in q:
            books.append(Book.query.filter_by(ISBN=row[0]).first())
            print(row)

    return render_template('home.html', form=s_form, books=books)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        record = User.query.filter_by(logname=form.username.data).first()
        if record is None:
            h = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            new_user = User(fname=form.firstname.data, lname=form.lastname.data,
                            phone=form.phone.data, addr=form.address.data,
                            logname=form.username.data,
                            logpass=h, access=0)
            db.session.add(new_user)
            db.session.commit()
            flash(f'Account Registered for {form.username.data}', 'success')
            return redirect(url_for('login'))
        else:
            flash(f'Account with username {form.username.data} already exists', 'danger')
    return render_template('register.html', form=form)


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        record = User.query.filter_by(logname=form.username.data).first()
        if record and bcrypt.check_password_hash(record.logpass, form.password.data):
            login_user(record)
            flash(f'Successful Login for {form.username.data}', 'success')
            return redirect(url_for('home'))
        else:
            flash(f'Incorrect Username or Password', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/user_profile/<userid>', methods=['GET', 'POST'])
@login_required
def profile(userid):
    if userid is None:
        userid = current_user.id
    img = url_for('static', filename="pictures/default_user_profile.jpg")
    u = User.query.filter_by(id=userid).first()
    t_form = TrustForm()

    if current_user != userid and t_form.validate_on_submit():
        t_score = None
        if t_form.trust_field.data == 'trust_user':
            t_score = 1
        elif t_form.trust_field.data == 'distrust_user':
            t_score = -1

        if u in current_user.trust_scored_users:
            db.session.query(trusts).filter_by(sender=current_user.id, receiver=u.id).update(dict(trustScore=t_score))
        else:
            ins = trusts.insert().values(sender=current_user.id, receiver=u.id, trustScore=t_score)
            db.session.execute(ins)
        db.session.commit()

    agg_t_score = 0
    received_t_scores = db.session.query(trusts).filter_by(receiver=u.id).all()
    for s in received_t_scores:
        if s.trustScore:
            agg_t_score += s.trustScore

    rec = db.session.query(trusts).filter_by(sender=current_user.id, receiver=u.id).first()
    prompt_text = 'Trust this User?'
    if rec is None:
        pass
    elif rec.trustScore == 1:
        prompt_text = 'Trust this user'
    elif rec.trustScore == -1:
        prompt_text = 'Do not trust this user'

    return render_template('profile.html', image_file=img, b=Book, u=u, t=trusts,
                           form=t_form, prompt_text=prompt_text, agg_t_score=agg_t_score)


@app.route('/popular', methods=['GET', 'POST'])
@login_required
def popular():
    recs = None
    if len(current_user.orders) != 0:
        recs = []
        txt = "The following books are popular right now."
        prev_o = Order.query.filter_by(user_id=current_user.id).all()[-1].book_isbn

        q = f"""
        SELECT DISTINCT b.ISBN
        FROM User u, Book b, `Order` o1, `Order` o2
        WHERE o1.book_isbn = '{prev_o}' AND
                u.id = o1.user_id AND 
                u.id <> {current_user.id} AND
                o1.book_isbn <> o2.book_isbn AND
                o2.user_id = u.id AND
                o2.book_isbn = b.ISBN
        GROUP BY b.ISBN
        ORDER BY COUNT(DISTINCT o2.orderID) DESC
        """

        query_txt = text(q)

        q = db.session.execute(query_txt)

        for row in q:
            recs.append(Book.query.filter_by(ISBN=row[0]).first())

    else:
        txt = "Order a book to receive recommendations"
    if recs is not None and len(recs) == 0:
        txt = "No popular or similar books found"
    return render_template('Popular.html', txt=txt, recs=recs)


@app.route('/orders')
@login_required
def orders():
    return render_template('orders.html', b=Book)


@app.route('/book/<book_isbn>', methods=['GET', 'POST'])
@login_required
def book(book_isbn):
    img = url_for('static', filename="pictures/books.png")
    b = Book.query.filter_by(ISBN=book_isbn).first()
    c = db.session.query(costs).filter_by(book_isbn=book_isbn).first()
    r_form = RateForm()
    o_form = OrderForm()
    f_form = TopNRatingsForm()
    ratings_list = []

    if b:
        # n-ratings filter form validate
        if f_form.validate_on_submit():
            n = str(f_form.n.data)
            q = f"""
                SELECT DISTINCT r.ratingID 
                FROM rating r LEFT OUTER JOIN
                    (SELECT AVG(u.useScore) AS avguscore, r.ratingID AS ratingID FROM rating r, usefulness u
                        WHERE r.ratingID = u.ratingID
                        GROUP BY r.ratingID
                    ) u ON r.ratingID = u.ratingID
                WHERE r.book_isbn = "{b.ISBN}"
                ORDER BY u.avguscore DESC
                LIMIT {n}
            """
            query_txt = text(q)

            q_list = db.session.execute(query_txt)
            for row in q_list:
                ratings_list.append(Rating.query.filter_by(ratingID=row[0]).first())

        # Review Form validate
        elif r_form.validate_on_submit():
            rec = Rating.query.filter_by(user_id=current_user.id, book_isbn=book_isbn).first()
            print(type(r_form.rate_score_field.data))
            if rec is None:
                if r_form.rate_comment_field != "":
                    r = Rating(ratingScore=r_form.rate_score_field.data, ratingComment=r_form.rate_comment_field.data,
                               book_isbn=book_isbn, user_id=current_user.id)
                else:
                    r = Rating(ratingScore=r_form.rate_score_field.data, book_isbn=book_isbn, user_id=current_user.id)

                db.session.add(r)
                db.session.commit()
                flash(f'Thank you for your review!', 'success')
            else:
                flash(f'You have already reviewed this book', 'danger')

        # Order form validate
        elif o_form.validate_on_submit():
            if b.stock - o_form.quantity_field.data > 0:
                order = Order(price=c.cost * o_form.quantity_field.data, time=datetime.now(),
                              amount=o_form.quantity_field.data, user_id=current_user.id, book_isbn=book_isbn)
                db.session.add(order)
                b.stock = b.stock - o_form.quantity_field.data
                db.session.commit()
                flash(f'Thank you for your order!', 'success')
            else:
                flash(f'That order cannot be satisfied with our current stock', 'danger')
        elif request.method == 'POST':
            flash(f'Make sure you are filling out your order or rating correctly', 'danger')
        if not f_form.validate_on_submit():
            ratings_list = b.ratings
        return render_template('books.html', f_form=f_form,
                               ratings_list=ratings_list, b=b, c=c, u=User,
                               image_file=img, form=r_form, form_order=o_form)
    else:
        return redirect(url_for('home'))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    today = date.today()
    last_quarter = today.replace(month=today.month - 3)
    a_form = AddBookForm()

    if current_user.access != 1:
        flash('You do not have permission to access that page', 'danger')
        redirect(url_for('home'))

    # The following are the user and book statistics queries

    most_pop_books = f"""
        SELECT b.ISBN
        FROM book b , `order` o
        WHERE b.ISBN = o.book_isbn AND
        o.time >=  '{last_quarter}'
        GROUP BY b.ISBN
        ORDER BY COUNT(DISTINCT o.orderID) DESC
        LIMIT 10
    """

    q = text(most_pop_books)
    q_result = db.session.execute(q)
    m_books = []
    for row in q_result:
        m_books.append((Book.query.filter_by(ISBN=row[0]).first()))

    s_form = StockLevelForm()
    p_form = PromoteUserForm()

    # Validate for the change stock form
    if s_form.validate_on_submit():
        b = Book.query.filter_by(ISBN=s_form.isbn_field.data).first()
        if b:
            b.stock += s_form.stock_change_field.data
            b.stock *= (b.stock > 0)
            db.session.commit()
            flash(f'Stock for {b.title} changed to {b.stock}', 'success')
        else:
            flash('Book not found!', 'danger')

    # Validate for the promote user form
    elif p_form.validate_on_submit():
        u = User.query.filter_by(logname=p_form.logname_field.data).first()
        if u:
            u.access = 1
            db.session.commit()
            flash(f'User {u.logname} promoted', 'Success')
        else:
            flash('User not found!', 'danger')

    # Validate for the Add Book form
    elif a_form.validate_on_submit():
        b = Book.query.filter_by(ISBN=a_form.ISBN.data).first()
        if b is not None:
            flash('A book with that ISBN already exists', 'danger')
        else:
            d = None
            flag = True
            if a_form.d.data != "":
                try:
                    d = datetime.strptime(a_form.d.data, '%m/%d/%Y')
                except: # Catches exception if user inputs incorrect date format
                    flag = False
            if flag:
                b = Book(ISBN=a_form.ISBN.data, title=a_form.title.data,
                         stock=a_form.stock.data, genre=a_form.genre.data, publisher=a_form.publisher.data,
                         language=a_form.language.data, date=d)
                c = costs.insert().values(book_isbn=b.ISBN, cost=a_form.price.data)
                db.session.execute(c)
                db.session.add(b)
                db.session.commit()
                flash(f'Successfully added {b.title}', 'success')
            else:
                flash(f'Incorrect date format', 'danger')

    return render_template('admin.html', a_form=a_form,
                           s_form=s_form, p_form=p_form, m_books=m_books)