from flask import Flask, render_template, request

import matplotlib.pyplot as plt
from io import BytesIO
import base64
from nba_api.stats.static import players
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.endpoints import playercareerstats
from matplotlib.patches import Circle, Rectangle, Arc
from flask import Flask, render_template, request, redirect, url_for, flash
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

def get_player_shotchartdetail(player_name, season_id):
    # player dictionary
    nba_players = players.get_players()
    player_dict = [player for player in nba_players if player['full_name'].lower() == player_name.lower()][0]

    # career dataframe
    career = playercareerstats.PlayerCareerStats(player_id=player_dict['id'])
    career_df = career.get_data_frames()[0]

    #team id during season
    team_id = career_df[career_df['SEASON_ID'] == season_id]['TEAM_ID']

    # shotchartdetail endpoints
    shotchartlist = shotchartdetail.ShotChartDetail(team_id=int(team_id),
                                                    player_id=int(player_dict['id']),
                                                    season_type_all_star='Regular Season',
                                                    season_nullable = season_id,
                                                    context_measure_simple='FGA').get_data_frames()

    return shotchartlist[0], shotchartlist[1]

# draw court function
def draw_court(ax=None, color="blue", lw=1, outer_lines=False):

    if ax is None:
        ax = plt.gca()

    # Basketball hoop
    hoop = Circle((0,0), radius=7.5, linewidth=lw, color=color, fill=False)

    # Backboard
    backboard = Rectangle((-30, -12.5), 60, 0, linewidth=lw, color=color)

    # The paint
    outer_box = Rectangle((-80,-47.5), 160, 190, linewidth=lw,color=color,fill=False)
    inner_box = Rectangle((-60, -47.5), 120, 190, linewidth=lw, color=color, fill=False)

    # Free throw line
    free_throw = Arc((0,142.5),120,120,theta1=0, theta2=180, linewidth=lw, color=color, fill=False)

    # Three point line
    corner_three_a = Rectangle((-220, -47.5), 0, 140, linewidth=lw, color=color)
    corner_three_b = Rectangle((220, -47.5), 0, 140, linewidth=lw,color=color)
    three_arc = Arc((0,0), 475, 475, theta1=22, theta2=158, linewidth=lw, color=color)
    court_elements = [hoop, backboard, outer_box, inner_box, free_throw, corner_three_a, corner_three_b, three_arc]

    for element in court_elements:
        ax.add_patch(element)

# Shot chart function
def shot_chart(data, title='',color='b', xlim=(-250,250), ylim=(422.5,-47.5),
               line_color='blue', court_color='white', court_lw=2, outer_lines=False,
               flip_court=False,gridsize=None,ax=None,despine=False):
    if ax is None:
        ax = plt.gca()

    if not flip_court:
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
    else:
        ax.set_xlim(xlim[::-1])
        ax.set_ylim(ylim[::-1])
    ax.tick_params(labelbottom="off", labelleft="off")
    ax.set_title(title, fontsize=18)

    #draws the court using draw_court()
    draw_court(ax,color=line_color, lw=court_lw, outer_lines=outer_lines)

    # seperate missed and made shots
    x_missed = data[data['EVENT_TYPE'] == 'Missed Shot']['LOC_X']
    y_missed = data[data['EVENT_TYPE'] == 'Missed Shot']['LOC_Y']

    x_made = data[data['EVENT_TYPE'] == 'Made Shot']['LOC_X']
    y_made = data[data['EVENT_TYPE'] == 'Made Shot']['LOC_Y']

    # Plot missed shots
    ax.scatter(x_missed, y_missed, c='r', marker='x', s=300, linewidths=3)

    # Plot made shots
    ax.scatter(x_made, y_made, facecolors='none', edgecolors='g', marker='o', s=100, linewidths=3)

    for spine in ax.spines:
        ax.spines[spine].set_lw(court_lw)
        ax.spines[spine].set_color(line_color)
    if despine:
        ax.spines['top'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

    return ax


def draw_plot(player_shotchart_df, title):
    plt.rcParams['figure.figsize'] = (12, 11)

    # Create a BytesIO object
    img = BytesIO()

    # Create a figure and axis
    fig, ax = plt.subplots()

    # Call the shot_chart function with the specified data and title
    shot_chart(player_shotchart_df, title=title, ax=ax)

    # Save the figure to the BytesIO object
    plt.savefig(img, format='png')

    # Close the figure to release resources
    plt.close(fig)

    # Move the BytesIO object cursor to the beginning
    img.seek(0)

    # Encode the image as base64
    image_data = base64.b64encode(img.getvalue()).decode()

    return image_data


def is_valid_season_id(season_id):
    try:
        start_year, end_year = map(int, season_id.split('-'))
        if not (start_year >= 1996 and start_year <= 2023) or not (end_year == start_year % 100 + 1):
            return False
        return True
    except ValueError:
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/result', methods=['POST'])
def result():
    try:
        player_name = request.form['player_name']
        season_id = request.form['season_id']

        # Validate inputs
        if not player_name or not season_id:
            error_message = 'Please enter both player name and season ID.'
            return render_template('index.html', error=error_message)

        # Check if both the player name and season_id are in valid formats
        nba_players = players.get_players()
        player_exists = any(player['full_name'].lower() == player_name.lower() for player in nba_players)

        if not is_valid_season_id(season_id) and not player_exists:
            error_message = 'Invalid player name and season. Please enter a valid NBA player name and a valid season in the format "YYYY-YY" within the range "1996-97" to "2023-24".'
            return render_template('index.html', error=error_message)

        if not is_valid_season_id(season_id):
            error_message = 'Invalid season. Please enter a valid season in the format "YYYY-YY" within the range "1996-97" to "2023-24".'
            return render_template('index.html', error=error_message)

        if not player_exists:
            error_message = 'Invalid player name. Please enter a valid NBA player name.'
            return render_template('index.html', error=error_message)

        # Get shot chart data
        player_shotchart_df, _ = get_player_shotchartdetail(player_name, season_id)

        title = f'{player_name} {season_id} Shot Chart'
        image_data = draw_plot(player_shotchart_df, title)

        return render_template('result.html', title=title, image_data=image_data)

    except Exception as e:
        # Handle other unexpected exceptions
        error_message = f'An error occurred: {str(e)}'
        return render_template('index.html', error=error_message)


if __name__ == '__main__':
    app.run(debug=True, port=8080)