
from gurobipy import Model, GRB
import pandas as pd

# ✅ Load Data
course_data_path = "/Users/huangfeixue/Desktop/学校/Edinburgh/Y4/Topics in Applied Operational Research/Project/filtered_course_data_S1_odd.csv"
student_data_path = "/Users/huangfeixue/Desktop/学校/Edinburgh/Y4/Topics in Applied Operational Research/Project/Student_S1.csv"

course_data = pd.read_csv(course_data_path)
student_data = pd.read_csv(student_data_path)

# ✅ Initialize Gurobi Model
model = Model("Student_Timetabling")
model.ModelSense = GRB.MAXIMIZE

# ✅ Define Sets
time_slots = range(1, 46)  # 9 hours/day * 5 days = 45 slots
students = student_data["student_index"].unique()
courses = course_data["course_index"].unique()

# ✅ Define Decision Variables
y_L, y_N, y_C = {}, {}, {}
x_L, x_N, x_C = {}, {}, {}  # New variables to assign courses to slots
for c in courses:
    for t in time_slots:
        x_L[c, t] = model.addVar(vtype=GRB.BINARY, name=f"x_L_{c}_{t}")
        x_N[c, t] = model.addVar(vtype=GRB.BINARY, name=f"x_N_{c}_{t}")
        x_C[c, t] = model.addVar(vtype=GRB.BINARY, name=f"x_C_{c}_{t}")

for s in students:
    for c in courses:
        for t in time_slots:
            y_L[s, c, t] = model.addVar(vtype=GRB.BINARY, name=f"y_L_{s}_{c}_{t}")
            y_N[s, c, t] = model.addVar(vtype=GRB.BINARY, name=f"y_N_{s}_{c}_{t}")
            y_C[s, c, t] = model.addVar(vtype=GRB.BINARY, name=f"y_C_{s}_{c}_{t}")

model.update()

# ✅ Objective Function: Maximize Student Attendance
objective = sum(y_L[s, c, t] for s in students for c in courses for t in time_slots)
objective += sum(y_N[s, c, t] for s in students for c in courses for t in time_slots)
objective += sum(y_C[s, c, t] for s in students for c in courses for t in time_slots)
model.setObjective(objective, GRB.MAXIMIZE)

# ✅ Constraints
# 1. Assign Courses to Time Slots
course_durations = course_data.set_index("course_index")[
    ["Lecture duration by week", "Normal Workshop Duration", "Computer Workshop Duration"]
].to_dict(orient="index")

for c in courses:
    lecture_duration = course_durations.get(c, {}).get("Lecture duration by week", 0)
    duration_N = course_durations.get(c, {}).get("Normal Workshop Duration", 0)
    duration_C = course_durations.get(c, {}).get("Computer Workshop Duration", 0)
    
    model.addConstr(sum(x_L[c, t] for t in time_slots) == lecture_duration)
    if duration_N > 0:
        model.addConstr(sum(x_N[c, t] for t in time_slots) == duration_N)
    if duration_C > 0:
        model.addConstr(sum(x_C[c, t] for t in time_slots) == duration_C)

# 2. Workshops Must Be Consecutive and Stay Within One Day
for c in courses:
    duration_N = course_durations.get(c, {}).get("Normal Workshop Duration", 0)
    duration_C = course_durations.get(c, {}).get("Computer Workshop Duration", 0)
    
    for t in time_slots:
        if duration_N > 0 and t + duration_N - 1 <= max(time_slots):  # Ensure within valid range
            model.addConstr(
                sum(x_N[c, t + k] for k in range(int(duration_N))) == duration_N * x_N[c, t]
            )
        if duration_C > 0 and t + duration_C - 1 <= max(time_slots):
            model.addConstr(
                sum(x_C[c, t + k] for k in range(int(duration_C))) == duration_C * x_C[c, t]
            )

# 3. Assign Students to Courses Based on Availability
for s in students:
    for c in courses:
        for t in time_slots:
            model.addConstr(y_L[s, c, t] <= x_L[c, t])
            model.addConstr(y_N[s, c, t] <= x_N[c, t])
            model.addConstr(y_C[s, c, t] <= x_C[c, t])

# 4. No Double Booking for Students
for s in students:
    for t in time_slots:
        model.addConstr(sum(y_L[s, c, t] + y_N[s, c, t] + y_C[s, c, t] for c in courses) <= 1)

# 5. If a Lecture and Workshop Overlap, Student Must Attend Workshop
for s in students:
    for c in courses:
        for t in time_slots:
            model.addConstr(y_N[s, c, t] + y_C[s, c, t] + y_L[s, c, t] <= 1)

# ✅ Solve Model
model.optimize()

if model.Status == GRB.INFEASIBLE:
    print("⚠️ Model is infeasible. Finding conflicts...")
    model.computeIIS()
    model.write("infeasible_constraints.ilp")  # Saves infeasible constraints to a file
    print("Check 'infeasible_constraints.ilp' to debug infeasibility.")
else:
    print(f"✅ Optimal solution found! Objective Value: {model.ObjVal}")



# ✅ Extract Results
results = []
for (c, t), var in x_L.items():
    if var.X > 0.5:
        results.append((c, t, "Lecture"))
for (c, t), var in x_N.items():
    if var.X > 0.5:
        results.append((c, t, "Workshop"))
for (c, t), var in x_C.items():
    if var.X > 0.5:
        results.append((c, t, "Computer Workshop"))

# ✅ Save Course Schedule to CSV
course_results_df = pd.DataFrame(results, columns=["Course", "TimeSlot", "Type"])
course_results_df.to_csv("/Users/huangfeixue/Desktop/学校/Edinburgh/Y4/Topics in Applied Operational Research/Project/course_schedule.csv", index=False)

# ✅ Save Student Attendance to CSV
student_results = []
for (s, c, t), var in y_L.items():
    if var.X > 0.5:
        student_results.append((s, c, t, "Lecture"))
for (s, c, t), var in y_N.items():
    if var.X > 0.5:
        student_results.append((s, c, t, "Workshop"))
for (s, c, t), var in y_C.items():
    if var.X > 0.5:
        student_results.append((s, c, t, "Computer Workshop"))

student_results_df = pd.DataFrame(student_results, columns=["Student", "Course", "TimeSlot", "Type"])
student_results_df.to_csv("/Users/huangfeixue/Desktop/学校/Edinburgh/Y4/Topics in Applied Operational Research/Project/student_schedule.csv", index=False)

print("✅ Optimized schedules saved as 'course_schedule.csv' and 'student_schedule.csv'.")
