###############################
####### SETUP (OVERALL) #######
###############################
import apikey
apikey = apikey.apikey

## Import statements
# Import statements
import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField,widgets,DateField,SelectMultipleField,SubmitField # Note that you may need to import more here! Check out examples that do what you want to figure out what.
from wtforms.validators import Required,Optional # Here, too
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell
import json
import requests
from datetime import datetime
from collections import defaultdict

## App setup code
app = Flask(__name__)
app.debug = True
app.use_reloader = True

## All app.config values

app.config['SECRET_KEY'] = 'UBYD&76*&SDg8S*GD8yG*Fg*DG87gCDG*G8d8YG&TAG*Q(H'
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:abc123@localhost/midterm364"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set up Flask debug stuff
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)


######################################
######## HELPER FXNS (If any) ########
######################################

def get_or_create_author(authorname,outletid):
    authorquery = Authors.query.filter_by(name=authorname).first()
    if authorquery:
        return authorquery
    else:
        author = Authors(name = authorname,outlet_id = outletid)
        db.session.add(author)
        db.session.commit()
        return author

def get_or_create_outlet(outletname,nameid):
    outletquery = Outlets.query.filter_by(name=outletname).first()
    if outletquery:
        return outletquery
    else:
        outlet = Outlets(name = outletname,nameid = nameid)
        db.session.add(outlet)
        db.session.commit()
        return outlet

def add_or_ignore_headlines(headlines):
    returnlist = []
    for headline in headlines['articles']:
        title = headline['title']
        author = headline['author']
        description = headline['description']
        url = headline['url']
        dt = headline['publishedAt'].strip('Z').split('T')
        date = dt[0].split('-')
        time = dt[1].split(':')
        dt = datetime(year = int(date[0]), month = int(date[1]), day = int(date[2]), hour = int(time[0]), minute = int(time[1]), second = int(time[2]))
        outletname = headline['source']['name']
        outletid = headline['source']['id']
        headlinequery = Headlines.query.filter_by(title=title,description=description,date=dt,url=url).first()
        if not headlinequery:
            outletidnum = get_or_create_outlet(outletname = outletname, nameid = outletid).id
            authorid = get_or_create_author(authorname = author,outletid = outletidnum).id
            headline = Headlines(title=title,description=description,url=url,date=dt,outlet_id=outletidnum,author_id=authorid)
            db.session.add(headline)
            db.session.commit()
            returnlist.append(headline)
        else:
            returnlist.append(headlinequery)
    return returnlist




##################
##### MODELS #####
##################


class Headlines(db.Model):
    __tablename__ = "headlines"
    id = db.Column(db.Integer,primary_key=True)
    title = db.Column(db.String(128))
    description = db.Column(db.String(1024))
    url = db.Column(db.String(1024))
    date = db.Column(db.DateTime())
    outlet_id = db.Column(db.Integer, db.ForeignKey("outlets.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"))

    def __repr__(self):
        return "{} (ID: {})".format(self.title, self.id)

class Outlets(db.Model):
    __tablename__ = "outlets"
    id = db.Column(db.Integer,primary_key=True)
    nameid = db.Column(db.String(64))
    name = db.Column(db.String(64))
    outlets = db.relationship('Headlines',backref='Outlets')
    authors = db.relationship('Authors',backref='Outlets')

    def __repr__(self):
        return "{} (ID: {})".format(self.name, self.id)

class Authors(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(128))
    headlines = db.relationship('Headlines',backref='Authors')
    outlet_id = db.Column(db.Integer, db.ForeignKey("outlets.id"))

    def __repr__(self):
        return "{} (ID: {})".format(self.name, self.id)



###################
###### FORMS ######
###################


class PullForm(FlaskForm):
    term = StringField("Please enter an article headline search term:",validators=[Required(message='Must enter term')])
    submit = SubmitField()

class SearchForm(FlaskForm):
    string = StringField("Enter headline text (or leave blank to search by any headline text):")
    outlets = SelectMultipleField('',choices = [],option_widget=widgets.CheckboxInput(), widget=widgets.ListWidget(prefix_label=False) )
    authors = SelectMultipleField('',choices = [],option_widget=widgets.CheckboxInput(), widget=widgets.ListWidget(prefix_label=False) )
    datefrom = DateField('',validators=[Optional()])
    dateto = DateField('',validators=[Optional()])
    def validate(self):
        if not FlaskForm.validate(self):
            return False
        result = True
        if self.datefrom.data is None or self.dateto.data is None:
            return result
        elif self.datefrom.data>self.dateto.data:
            self.datefrom.errors.append('"From" date must be prior to or same as "To" date')
            result = False
        return result
    submit = SubmitField()

#######################
###### VIEW FXNS ######
#######################


@app.route('/') ## Form for search term to pull from API
def pull():
    form = PullForm()
    return render_template('articlepull.html',form=form)

@app.route('/pull_results',methods=['GET','POST']) ## Searches articles that are pulled by search term 
def results():
    form = PullForm(request.args)
    if form.validate():   
        term = request.args['term']
        url = 'https://newsapi.org/v2/top-headlines?country=us&apiKey={}&q={}'.format(apikey,term)
        headlines = json.loads((requests.get(url)).text) ## Only gets first 20 results if more than 20 results
        if headlines['status'] != 'ok':
            headlines = 'Error, something went wrong'
        else:
            headlines = add_or_ignore_headlines(headlines)
        return render_template('articleresults.html',headlines=headlines,headlinelen=len(headlines))
    flash([error for errors in form.errors.values() for error in errors])
    return redirect(url_for('pull'))

@app.route('/search',methods=['GET','POST']) ## Searches the already collected articles in the database
def search():
    result='none'
    form = SearchForm()
    outlets = []
    authors = []
    if not Headlines.query.all():
        return render_template('articlesearch.html',entries = False,results=result)
    for headline in Headlines.query.all():
        outlet = Outlets.query.filter_by(id=headline.outlet_id).first()
        author = Authors.query.filter_by(id=headline.author_id).first()
        outlet = (str(outlet.id),outlet.name)
        author = (str(author.id),author.name)
        if outlet not in outlets:
            outlets.append(outlet)
        if author not in authors:
            authors.append(author)
    form.outlets.choices = outlets
    form.authors.choices = authors
    if form.validate_on_submit():
        string = form.string.data
        outlets = form.outlets.data
        authors = form.authors.data
        datefrom = form.datefrom.data
        dateto = form.dateto.data
        headlinelist = []
        for headline in Headlines.query.all():
            if string and string.lower() not in headline.title.lower():
                continue
            if outlets and len([True for outlet in outlets if (int(outlet) == headline.outlet_id)]) == 0:
                continue
            if authors and len([True for author in authors if (int(author) == headline.author_id)]) == 0:
                continue
            if datefrom and not headline.date.date()>=datefrom:
                continue
            if dateto and not headline.date.date()<=dateto:
                continue
            headlinelist.append((headline.title,headline.date.date(),headline.date.time(),Authors.query.filter_by(id=headline.author_id).first().name,Outlets.query.filter_by(id=headline.outlet_id).first().name))
        return render_template('articlesearch.html',form=form,results=headlinelist, entries=True)
    flash([error for errors in form.errors.values() for error in errors])
    return render_template('articlesearch.html',form=form,results=result,entries=True)

@app.route('/outlets_authors') ## Searches the already collected articles in the database
def outletsauthors():
    outlets = defaultdict(list)
    authors = Authors.query.all()
    for author in authors:
        outletid=author.outlet_id
        outlets[Outlets.query.filter_by(id=outletid).first().name].append(author.name)
    return render_template('outlets_authors.html',outlets=outlets.items(),outletlen=len(outlets.items()))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404



## Code to run the application...

# Put the code to do so here!
# NOTE: Make sure you include the code you need to initialize the database structure when you run the application!
if __name__ == '__main__':
    db.create_all()
    manager.run()
