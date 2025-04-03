import streamlit as st
import pandas as pd
from utils.calculations import calculate_bmr, calculate_tdee, calculate_protein_needs
from utils.meal_planning import generate_meal_plan
from utils.recipe_recommendations import get_recipe_recommendations, format_recipe_recommendation
from utils.db_operations import create_user, save_meal_plan, get_latest_meal_plan
from utils.progress_tracking import add_progress_entry, get_user_progress, calculate_progress_metrics
from utils.auth import init_session_state, login_user, logout_user, register_user, get_current_user, require_auth
from models.database import get_db
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from utils.meal_customization import get_alternative_meals, validate_meal_plan
from utils.history_viewer import get_user_meal_plans, get_user_progress_history, format_meal_plan_for_display
from utils.workout_planner import generate_workout_plan, save_workout_schedule, get_latest_workout_schedule, exercise_library, training_guidelines
from utils.recovery_recommendations import calculate_recovery_score, generate_recovery_recommendations

# Set page config
st.set_page_config(page_title="Fitness & Nutrition Planner", layout="wide")

# Initialize session state
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_authenticated' not in st.session_state:
    st.session_state.is_authenticated = False
if 'current_schedule' not in st.session_state:
    st.session_state.current_schedule = None
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None
if 'current_meal_plan' not in st.session_state:
    st.session_state.current_meal_plan = None
if 'nutritional_targets' not in st.session_state:
    st.session_state.nutritional_targets = None

def display_exercise_library():
    """Display the exercise library organized by muscle groups and subgroups"""
    st.header("💪 Exercise Library")

    # Add tabs for Exercise Library and Training Guidelines
    tab_exercises, tab_guidelines = st.tabs(["Exercises by Muscle Group", "Training Guidelines"])

    with tab_exercises:
        # Select fitness level
        fitness_level = st.selectbox(
            "Select Fitness Level",
            ["Beginner", "Intermediate", "Advanced"]
        )

        # Select equipment
        equipment = st.multiselect(
            "Available Equipment",
            ["None/Bodyweight", "Dumbbells", "Full Gym Access"],
            default=["None/Bodyweight"]
        )

        # Display muscle groups and their subgroups
        for muscle_group, subgroups in exercise_library.items():
            with st.expander(f"{muscle_group} Muscle Group"):
                for subgroup, exercises_dict in subgroups.items():
                    st.subheader(f"⚡ {subgroup}")
                    if fitness_level in exercises_dict:
                        exercises_shown = False
                        for equip in equipment:
                            if equip in exercises_dict[fitness_level]:
                                exercises = exercises_dict[fitness_level][equip]
                                st.write(f"🔹 {equip} Exercises:")
                                for exercise in exercises:
                                    st.write(f"  • {exercise}")
                                exercises_shown = True

                        if not exercises_shown:
                            st.info(f"No exercises available for selected equipment at {fitness_level} level")
                    else:
                        st.warning(f"No exercises available for {fitness_level} level")
                    st.write("---")

    with tab_guidelines:
        st.header("🎯 Training Guidelines")
        st.write("Select your training goal to see specific guidelines for sets, reps, and rest periods.")

        # Create columns for better organization
        col1, col2 = st.columns(2)

        with col1:
            selected_goal = st.selectbox(
                "Select Training Goal",
                list(training_guidelines.keys())
            )

        with col2:
            st.info("💡 These guidelines are general recommendations. Adjust based on your experience and recovery ability.")

        if selected_goal:
            guidelines = training_guidelines[selected_goal]

            # Display guidelines in an organized format
            st.subheader(f"Guidelines for {selected_goal}")

            # Create three columns for organized display
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Rep Range", guidelines["rep_range"])
                st.metric("Sets per Exercise", guidelines["sets_per_exercise"])

            with col2:
                st.metric("Rest Period", guidelines["rest_period"])
                st.metric("Training Frequency", guidelines["frequency"])

            with col3:
                st.metric("Intensity", guidelines["intensity"])
                st.metric("Movement Tempo", guidelines["tempo"])

            # Display summary
            st.write("### Summary")
            st.info(guidelines["summary"])

            # Additional tips
            st.write("### Important Notes")
            st.write("""
            - Always warm up properly before training
            - Start with lighter weights to warm up before working sets
            - Listen to your body and adjust weights/reps as needed
            - Focus on proper form over weight/reps
            - Stay hydrated during your workout
            - Track your progress to ensure improvement
            """)

def get_database():
    """Get database session with improved error handling"""
    try:
        db = next(get_db())
        return db
    except Exception as e:
        st.error(f"Database connection error: {str(e)}")
        st.error("Please try again in a few moments.")
        return None


def create_progress_charts(progress_data):
    """Create progress tracking charts using plotly"""
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=('Weight Progress', 'Calorie Intake', 'Protein Intake')
    )

    fig.add_trace(
        go.Scatter(x=progress_data['dates'], y=progress_data['weights'], name='Weight (kg)'),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(x=progress_data['dates'], y=progress_data['calories'], name='Calories'),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(x=progress_data['dates'], y=progress_data['protein'], name='Protein (g)'),
        row=3, col=1
    )

    fig.update_layout(height=800, showlegend=True)
    return fig


def display_meal_plan():
    """Display and handle meal plan customization"""
    if not st.session_state.current_meal_plan:
        return

    st.header("Your Meal Plan")
    st.info("💡 Click on any meal to see alternatives and customize your plan!")

    # Add a timestamp to ensure unique keys
    timestamp = int(time.time())

    for day, meals in st.session_state.current_meal_plan.items():
        st.write(f"### {day}")
        for meal_type, meal in meals.items():
            with st.container():
                st.write(f"#### {meal_type}")
                st.write(f"🍽️ **Current:** {meal['name']}")
                st.write(f"Calories: {meal['calories']} kcal")
                st.write(f"Protein: {meal['protein']}g")
                if meal.get('link'):
                    st.write(f"[Recipe Link]({meal['link']})")

                # Button for alternatives with unique key combining timestamp, day, and meal type
                btn_key = f"btn_{timestamp}_{day}_{meal_type}"
                if st.button(f"Show alternatives for {meal_type}", key=btn_key):
                    alternatives = get_alternative_meals(
                        meal_type=meal_type,
                        target_calories=st.session_state.nutritional_targets['calories'] / 3,
                        target_protein=st.session_state.nutritional_targets['protein'] / 3,
                        dietary_restrictions=st.session_state.user_profile['dietary_restrictions'],
                        cuisine_preferences=st.session_state.user_profile['cuisine_preferences'],
                        current_meal_name=meal['name']
                    )

                    if alternatives:
                        st.write("Alternative options:")
                        for alt in alternatives:
                            st.write(f"- {alt['name']} ({alt['calories']} kcal, {alt['protein']}g protein)")
                            select_key = f"select_{timestamp}_{day}_{meal_type}_{alt['name']}"
                            if st.button(f"Select {alt['name']}", key=select_key):
                                st.session_state.current_meal_plan[day][meal_type] = alt
                                st.success(f"Updated meal to {alt['name']}")
                                st.rerun()
                    else:
                        st.warning("No alternative meals found matching your criteria")


def calculate_nutrition():
    """Calculate nutritional needs and generate meal plan"""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Personal Information")
        weight = st.number_input("Weight (kg)", min_value=30.0, max_value=250.0, value=70.0, step=0.1)
        height = st.number_input("Height (cm)", min_value=100.0, max_value=250.0, value=170.0, step=0.1)
        age = st.number_input("Age", min_value=15, max_value=100, value=30)
        gender = st.selectbox("Gender", ["Male", "Female"])

        activity_levels = {
            "Sedentary (office job, little exercise)": 1.2,
            "Light Exercise (1-2 days/week)": 1.375,
            "Moderate Exercise (3-5 days/week)": 1.55,
            "Heavy Exercise (6-7 days/week)": 1.725,
            "Athlete (2x training/day)": 1.9
        }
        activity = st.selectbox("Activity Level", list(activity_levels.keys()))

    with col2:
        st.subheader("Goals & Preferences")
        goal = st.selectbox("Fitness Goal", [
            "Lose Weight",
            "Maintain Weight",
            "Gain Muscle"
        ])

        dietary_restrictions = st.multiselect(
            "Dietary Restrictions",
            ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "None"],
            default=["None"]
        )

        cuisine_preferences = st.multiselect(
            "Cuisine Preferences",
            ["Mediterranean", "Asian", "American", "Mexican", "Indian", "Any"],
            default=["Any"]
        )

    if st.button("Calculate My Needs"):
        with st.spinner("Calculating your personalized plan..."):
            try:
                # Calculate nutritional needs
                bmr = calculate_bmr(weight, height, age, gender)
                activity_factor = activity_levels[activity]
                tdee = calculate_tdee(bmr, activity_factor)

                # Adjust calories based on goal
                if goal == "Lose Weight":
                    target_calories = tdee - 500
                elif goal == "Gain Muscle":
                    target_calories = tdee + 300
                else:
                    target_calories = tdee

                protein_needs = calculate_protein_needs(weight, goal)

                # Store user profile and targets in session state
                st.session_state.user_profile = {
                    'weight': weight,
                    'height': height,
                    'age': age,
                    'gender': gender,
                    'activity_level': activity,
                    'goal': goal,
                    'dietary_restrictions': dietary_restrictions,
                    'cuisine_preferences': cuisine_preferences
                }

                st.session_state.nutritional_targets = {
                    'calories': target_calories,
                    'protein': protein_needs,
                    'bmr': bmr
                }

                # Display results
                st.header("Your Personalized Results")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Daily Calories", f"{int(target_calories)} kcal")
                with col2:
                    st.metric("Daily Protein", f"{int(protein_needs)}g")
                with col3:
                    st.metric("Base Metabolic Rate", f"{int(bmr)} kcal")

                # Generate new meal plan only if requested or none exists
                if not st.session_state.current_meal_plan:
                    meal_plan = generate_meal_plan(
                        target_calories,
                        protein_needs,
                        dietary_restrictions,
                        cuisine_preferences
                    )
                    if meal_plan:
                        st.session_state.current_meal_plan = meal_plan
                    else:
                        st.error("Failed to generate meal plan. Please try again.")
                        return

                # Display current meal plan
                display_meal_plan()

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

def save_and_update_workout_schedule(db, user_id, schedule, preferences, is_custom=False):
    """Helper function to save and update workout schedule"""
    try:
        if save_workout_schedule(db, user_id, schedule, preferences, is_custom):
            return get_latest_workout_schedule(db, user_id)
        return None
    except Exception as e:
        print(f"Error in save_and_update_workout_schedule: {str(e)}")
        return None

def display_workout_schedule(schedule, selected_days=None):
    """Helper function to display workout schedule"""
    if not schedule:
        st.info("No workout schedule found. Create one to get started!")
        return

    st.write(f"{'🎯 Generated Plan' if not schedule.get('is_custom', False) else '✏️ Custom Plan'}")
    st.write(f"Schedule generated on: {schedule['date']}")

    # Only show workouts for selected days
    display_days = selected_days if selected_days else schedule['schedule'].keys()

    for day in display_days:
        if day in schedule['schedule']:
            workout = schedule['schedule'][day]
            with st.expander(f"{day}'s Workout", expanded=True):
                st.write(f"**Focus:** {workout['focus']}")
                st.write(f"**Duration:** {workout['duration']} minutes")
                st.write("**Exercises:**")
                for exercise in workout['exercises']:
                    # Display exercises with proper formatting
                    if isinstance(exercise, str):
                        if ":" in exercise:  # Check if exercise is from library
                            st.write(f"- {exercise}")  # Already formatted from library
                        else:
                            st.write(f"- {exercise}")  # Default exercise format


def generate_new_workout(db, fitness_level, goals, available_days, equipment, time_per_session, muscle_groups):
    """Helper function to generate and save a new workout schedule"""
    try:
        print("\n=== Starting New Workout Generation ===")
        print("Input parameters:")
        print(f"- Fitness level: {fitness_level}")
        print(f"- Goals: {goals}")
        print(f"- Available days: {available_days}")
        print(f"- Equipment: {equipment}")
        print(f"- Time per session: {time_per_session}")
        print(f"- Muscle groups: {muscle_groups}")

        # Input validation
        if not available_days:
            st.error("Please select at least one day for your workout")
            return None

        if not muscle_groups:
            st.error("Please select muscle groups for your workout days")
            return None

        # Clear current schedule from session state
        try:
            st.session_state.current_schedule = None
            print("Successfully cleared existing workout schedule")
        except Exception as e:
            print(f"Error clearing workout schedule: {str(e)}")

        with st.spinner("Generating your personalized workout plan..."):
            # Validate exercise library before generating schedule
            if not validate_exercise_library(exercise_library):
                st.error("Error with exercise data. Please try again.")
                return None

            # Generate new schedule using exercise library
            schedule = generate_workout_plan(
                fitness_level=fitness_level,
                goals=goals,
                available_days=available_days,
                equipment_available=equipment,
                time_per_session=time_per_session,
                muscle_groups=muscle_groups,
                exercise_library=exercise_library
            )

            if not schedule:
                st.error("Could not generate workout schedule. Please try different selections.")
                return None

            # Save preferences
            preferences = {
                "fitness_level": fitness_level,
                "goals": goals,
                "equipment": equipment,
                "time_per_session": time_per_session,
                "muscle_groups": muscle_groups
            }

            # Save to database and update session state
            if save_workout_schedule(db, st.session_state.user_id, schedule, preferences):
                print("Successfully saved new workout schedule")
                st.session_state.current_schedule = schedule
                st.success("✅ New workout plan generated successfully!")
                print("Updated session state with new schedule")
                st.experimental_rerun()
                return schedule
            else:
                st.error("Failed to save workout schedule")
                return None

    except Exception as e:
        print(f"Error in generate_new_workout: {str(e)}")
        st.error("An error occurred while generating your workout")
        return None

def validate_exercise_library(exercise_library):
    """Validates the exercise library data for completeness and consistency."""
    # Add your validation logic here.  This is a placeholder.
    #  A real implementation would check for missing keys, 
    #  data types, etc.  Return True if valid, False otherwise.
    return True  # Placeholder - replace with actual validation


def main():
    st.title("🏋️‍♂️ Fitness & Nutrition Planner")

    # Authentication forms
    if not st.session_state.is_authenticated:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])

        with tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login"):
                db = None
                try:
                    db = get_database()
                    if db:
                        if login_user(db, username, password):
                            st.session_state.username = username
                            st.session_state.is_authenticated = True
                            st.session_state.user_id = get_current_user(db).id
                            st.success("Successfully logged in!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
                except Exception as e:
                    st.error(f"Login error: {str(e)}")
                finally:
                    if db:
                        try:
                            db.close()
                        except Exception as close_error:
                            print(f"Error closing database: {str(close_error)}")

        with tab2:
            st.subheader("Create Account")
            new_username = st.text_input("Username", key="signup_username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password")

            if st.button("Sign Up"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                    return

                db = get_database()
                if db:
                    try:
                        user = register_user(db, new_username, new_email, new_password)
                        if user:
                            st.success("Account created successfully! Please log in.")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))
                    finally:
                        db.close()
        return

    # Main application (only shown when authenticated)
    if st.session_state.is_authenticated:
        st.sidebar.write(f"Welcome, {st.session_state.username}!")
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()

        # Main navigation
        tab_workout, tab_nutrition, tab_progress, tab_history, tab_library, tab_recovery = st.tabs([
            "Workout Planner",
            "Nutrition Planner",
            "Progress Tracking",
            "History",
            "Exercise Library",
            "Recovery Recommendations"
        ])

        with tab_library:
            display_exercise_library()

        with tab_workout:
            st.header("💪 Workout Schedule")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Create Workout Schedule")

                # Get user preferences
                fitness_level = st.selectbox(
                    "Your fitness level",
                    ["Beginner", "Intermediate", "Advanced"]
                )

                goals = st.multiselect(
                    "Your fitness goals",
                    ["Weight Loss", "Muscle Gain", "General Fitness", "Endurance"],
                    default=["General Fitness"]
                )

                # Select workout days
                st.write("Select your workout days:")
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                available_days = []

                col_days1, col_days2 = st.columns(2)
                with col_days1:
                    for day in days[:4]:
                        if st.checkbox(day, key=f"day_{day}"):
                            available_days.append(day)
                with col_days2:
                    for day in days[4:]:
                        if st.checkbox(day, key=f"day_{day}"):
                            available_days.append(day)

                equipment = st.multiselect(
                    "Available equipment",
                    ["None/Bodyweight", "Dumbbells", "Full Gym Access"],
                    default=["None/Bodyweight"]
                )

                time_per_session = st.slider(
                    "Minutes per session",
                    min_value=15,
                    max_value=120,
                    value=45,
                    step=15
                )

                # Muscle group selection
                muscle_groups = {}
                if available_days:
                    st.subheader("Muscle Group Selection")
                    available_muscle_groups = [
                        "Chest", "Back", "Legs",
                        "Biceps", "Triceps", "Shoulders",
                        "Core", "Rest"
                    ]

                    for day in available_days:
                        muscle_groups[day] = st.multiselect(
                            f"Target muscle groups for {day}",
                            available_muscle_groups,
                            key=f"muscle_groups_{day}"
                        )

                if st.button("Generate Workout Plan"):
                    if not available_days:
                        st.error("Please select at least one workout day")
                    elif not any(muscles for muscles in muscle_groups.values()):
                        st.error("Please select at least one muscle group")
                    else:
                        with st.spinner("Generating your personalized workout plan..."):
                            db = get_database()
                            if db:
                                try:
                                    new_schedule = generate_new_workout(
                                        db=db,
                                        fitness_level=fitness_level,
                                        goals=goals,
                                        available_days=available_days,
                                        equipment=equipment,
                                        time_per_session=time_per_session,
                                        muscle_groups=muscle_groups
                                    )

                                    if new_schedule:
                                        # Save the new schedule
                                        preferences = {
                                            "fitness_level": fitness_level,
                                            "goals": goals,
                                            "equipment": equipment,
                                            "time_per_session": time_per_session
                                        }

                                        if save_workout_schedule(db, st.session_state.user_id, new_schedule, preferences):
                                            st.session_state.current_schedule = new_schedule
                                            st.success("New workout plan generated successfully!")
                                            st.rerun()
                                    else:
                                        st.error("Could not generate workout plan. Please try different selections.")
                                except Exception as e:
                                    st.error(f"Error generating workout: {str(e)}")
                                finally:
                                    db.close()

            with col2:
                st.subheader("Current Workout Plan")
                db = get_database()
                if db:
                    try:
                        current_schedule = get_latest_workout_schedule(db, st.session_state.user_id)
                        display_workout_schedule(current_schedule, available_days)
                    finally:
                        db.close()

        with tab_nutrition:
            st.header("🥗 Nutrition Planner")
            calculate_nutrition()
            if st.session_state.current_meal_plan:
                display_meal_plan()
                if st.button("Save Current Meal Plan"):
                    db = get_database()
                    if db:
                        try:
                            user = get_current_user(db)
                            if user:
                                meal_plan_result = save_meal_plan(
                                    db=db,
                                    user_id=user.id,
                                    meal_plan=st.session_state.current_meal_plan,
                                    calories=st.session_state.nutritional_targets['calories'],
                                    protein=st.session_state.nutritional_targets['protein']
                                )
                                if meal_plan_result:
                                    st.success("Meal plan saved successfully!")
                        except Exception as e:
                            st.error(f"Error saving meal plan: {str(e)}")
                        finally:
                            db.close()

        with tab_progress:
            st.header("📊 Progress Tracking")
            require_auth()

            db = get_database()
            if db:
                try:
                    # Progress entry form
                    st.subheader("Log Today's Progress")
                    current_weight = st.number_input("Current Weight (kg)", min_value=30.0, max_value=250.0, step=0.1)
                    calories_consumed = st.number_input("Calories Consumed", min_value=0.0, max_value=10000.0, step=50.0)
                    protein_consumed = st.number_input("Protein Consumed (g)", min_value=0.0, max_value=500.0, step=5.0)
                    notes = st.text_area("Notes (optional)", height=100)

                    if st.button("Log Progress"):
                        progress_entry = add_progress_entry(
                            db=db,
                            user_id=st.session_state.user_id,
                            current_weight=current_weight,
                            calories_consumed=calories_consumed,
                            protein_consumed=protein_consumed,
                            notes=notes
                        )
                        if progress_entry:
                            st.success("Progress logged successfully!")

                    # Display progress charts
                    progress_data = get_user_progress(db, st.session_state.user_id)
                    if progress_data['dates']:
                        metrics = calculate_progress_metrics(progress_data)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Weight Change", f"{metrics['weight_change']} kg")
                        with col2:
                            st.metric("Avg. Daily Calories", f"{metrics['avg_calories']} kcal")
                        with col3:
                            st.metric("Avg. Daily Protein", f"{metrics['avg_protein']}g")

                        fig = create_progress_charts(progress_data)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No progress data available yet. Start logging your progress!")

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                finally:
                    db.close()

        with tab_history:
            st.header("📋 Your History")
            require_auth()

            db = get_database()
            if db:
                try:
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("📅 Saved Meal Plans")
                        meal_plans = get_user_meal_plans(db, st.session_state.user_id)

                        if meal_plans:
                            for plan in meal_plans:
                                formatted_plan = format_meal_plan_for_display(plan)
                                with st.expander(f"Meal Plan - {formatted_plan['date']}"):
                                    st.write(f"Daily Calories: {formatted_plan['daily_calories']} kcal")
                                    st.write(f"Daily Protein: {formatted_plan['daily_protein']}g")

                                    for day, meals in formatted_plan['meals'].items():
                                        st.write(f"\n**{day}**")
                                        for meal_type, meal in meals.items():
                                            st.write(f"- {meal_type}: {meal['name']}")
                                            st.write(f"  Calories: {meal['calories']} kcal, Protein: {meal['protein']}g")
                                            if meal.get('link'):
                                                st.write(f"  [Recipe Link]({meal['link']})")
                        else:
                            st.info("No saved meal plans yet. Save a meal plan to see it here!")

                        # Add Workout History section
                        st.subheader("💪 Workout History")
                        workout_schedules = get_latest_workout_schedule(db, st.session_state.user_id)

                        if workout_schedules:
                            with st.expander(f"Workout Schedule - {workout_schedules['date']}"):
                                st.write("**Type:** " + ("Custom Plan" if workout_schedules['is_custom'] else "Generated Plan"))
                                if workout_schedules['preferences'].get('fitness_level'):
                                    st.write(f"**Fitness Level:** {workout_schedules['preferences']['fitness_level']}")
                                if workout_schedules['preferences'].get('goals'):
                                    st.write(f"**Goals:** {', '.join(workout_schedules['preferences']['goals'])}")

                                st.write("\n**Workout Schedule:**")
                                for day, workout in workout_schedules['schedule'].items():
                                    st.write(f"\n*{day}*")
                                    st.write(f"Focus: {workout['focus']}")
                                    st.write(f"Duration: {workout['duration']} minutes")
                                    st.write("Exercises:")
                                    for exercise in workout['exercises']:
                                        st.write(f"- {exercise}")
                        else:
                            st.info("No workout history yet. Create a workout plan to see it here!")

                    with col2:
                        st.subheader("📊 Progress Log History")
                        progress_history = get_user_progress_history(db, st.session_state.user_id)

                        if progress_history:
                            for entry in progress_history:
                                with st.expander(f"Progress Log - {entry['date']}"):
                                    st.write(f"Weight: {entry['weight']} kg")
                                    st.write(f"Calories Consumed: {entry['calories']} kcal")
                                    st.write(f"Protein Consumed: {entry['protein']}g")
                                    if entry['notes']:
                                        st.write(f"Notes: {entry['notes']}")
                        else:
                            st.info("No progress logs yet. Start tracking your progress to see your history!")

                except Exception as e:
                    st.error(f"Error loading history: {str(e)}")
                finally:
                    db.close()

        with tab_recovery:
            st.header("🔄 Recovery Recommendations")

            # Get workout information
            workout_intensity = st.selectbox(
                "Last Workout Intensity",
                ["light", "moderate", "high", "very high"],
                key="recovery_intensity"
            )

            selected_exercises = st.multiselect(
                "Types of Exercises Performed",
                ["compound", "isolation", "bodyweight", "cardio"],
                default=["compound"],
                key="exercise_types"
            )

            # Get user metrics
            st.subheader("Your Current Metrics")
            col1, col2, col3 = st.columns(3)

            with col1:
                sleep_hours = st.number_input(
                    "Hours of Sleep Last Night",
                    min_value=0,
                    max_value=24,
                    value=7,
                    step=1
                )

            with col2:
                stress_level = st.selectbox(
                    "Current Stress Level",
                    ["low", "moderate", "high"],
                    key="stress_level"
                )

            with col3:
                nutrition_status = st.selectbox(
                    "Today's Nutrition Quality",
                    ["poor", "moderate", "good"],
                    key="nutrition_status"
                )

            if st.button("Get Recovery Recommendations"):
                # Prepare workout data
                workout_data = {
                    "intensity": workout_intensity,
                    "exercise_types": selected_exercises,
                    "exercises": selected_exercises  # For compatibility with the function
                }

                #                # Prepare user metrics
                user_metrics = {
                    "sleep_hours": sleep_hours,
                    "stress_level": stress_level,
                    "nutrition_status": nutrition_status
                }

                # Generate recommendations
                recommendations = generate_recovery_recommendations(workout_data, user_metrics)

                # Display recommendations
                st.subheader("Your Recovery Score")
                st.metric("Recovery Score", f"{recommendations['recovery_score']}/100")

                col1, col2 = st.columns(2)

                with col1:
                    st.write("### Recommended Rest Days")
                    st.info(f"{recommendations['recommended_rest_days']} days")

                    st.write("### Next Workout Date")
                    st.info(recommendations['next_workout_date'])

                    st.write("### Sleep Recommendations")
                    st.write(f"Minimum: {recommendations['sleep_recommendations']['minimum_hours']} hours")
                    st.write(f"Optimal: {recommendations['sleep_recommendations']['optimal_hours']} hours")

                with col2:
                    st.write("### Nutrition Tips")
                    for tip in recommendations['nutrition_tips']:
                        st.write(f"• {tip}")

                st.write("### Recovery Activities")
                for activity in recommendations['recovery_activities']:
                    st.write(f"• {activity}")

                st.write("### Sleep Optimization Tips")
                for tip in recommendations['sleep_recommendations']['tips']:
                    st.write(f"• {tip}")

if __name__ == "__main__":
    main()