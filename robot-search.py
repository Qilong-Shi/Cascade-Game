#
#   A quick and dirty demo of a search agent
#   for a single-robot warehouse.
#

ACTIONS = ['UP', 'DOWN', 'LEFT', 'RIGHT',
           'LIFT_UP', 'LIFT_DOWN', 'LIFT_LEFT', 'LIFT_RIGHT']

#   Grid dimensions of warehouse, where (0,0) is the top-left grid cell

NROWS = 2
NCOLS = 3


#
#   State of the warehouse is defined by the robot position
#   and a list of the positions of the boxes in the warehouse
#

INITIAL_STATE = ((0,1), (0,2), tuple())


#
#   Each node represented as a tuple:
#       (state, parent, action, depth, children)
#

#   Indexes of entries in node tuple

STATE = 0
PARENT = 1
ACTION = 2
DEPTH = 3
CHILDREN = 4

#   Indexes of entries in state tuple

STATE_TARGET = 0
STATE_ROBOT = 1
STATE_BOXES = 2

#   Goal position for target box

GOAL = (0,0)


#   Maximum number of nodes that can be expanded before termination
MAX_EXPANSIONS = 1000


#
#   Apply the given action to the given node, creating a new node.
#   If the action is not feasible in the state of the given node,
#   (e.g., moving a box into a position that is already occupued)
#   then the position of the robot and the target box in the new node
#   is the same as the given node.
#

def apply(action, node):
    
    ((target, robot, boxes), parent_action, grandparent, depth, children) = node
    (row, col) = robot
    new_robot = robot
    new_target = target
    new_boxes = boxes
    new_depth = depth + 1
   
    if   action == 'UP' and row > 0:
        new_robot = (row - 1, col)
    elif action == 'DOWN' and row < NROWS - 1:
        new_robot = (row + 1, col)
    elif action == 'LEFT' and col > 0:
        new_robot = (row, col - 1)
    elif action == 'RIGHT' and col < NCOLS - 1:
        new_robot = (row, col + 1)
    elif (action == 'LIFT_UP' and row > 0
          and robot in [target] + list(boxes)
          and (row - 1, col) not in [target] + list(boxes)):
        new_robot = (row - 1, col)
        if target == robot:
            new_target = new_robot
        else:
            new_boxes = update_boxes(boxes, robot, new_robot)
    elif (action == 'LIFT_DOWN' and row < NROWS - 1
          and robot in [target] + list(boxes)
          and (row + 1, col) not in [target] + list(boxes)):
        new_robot = (row + 1, col)
        if target == robot:
            new_target = new_robot
        else:
            new_boxes = update_boxes(boxes, robot, new_robot)
    elif (action == 'LIFT_LEFT' and col > 0
          and robot in [target] + list(boxes)
          and (row, col - 1) not in [target] + list(boxes)):
        new_robot = (row, col - 1)
        if target == robot:
            new_target = new_robot
        else:
            new_boxes = update_boxes(boxes, robot, new_robot)
    elif (action == 'LIFT_RIGHT' and col < NCOLS - 1
          and robot in [target] + list(boxes)
          and (row, col + 1) not in [target] + list(boxes)):
        new_robot = (row, col + 1)
        if target == robot:
            new_target = new_robot
        else:
            new_boxes = update_boxes(boxes, robot, new_robot)

    new_node = ((new_target, new_robot, new_boxes),
                node, action, new_depth, [])
    
    return new_node


#
#   Update the list of box positions by moving the box at position old_box
#   to the position new_box.
#

def update_boxes(boxes, old_box, new_box):
    
    return tuple(map(lambda box: new_box if box == old_box else box, boxes))


#
#   Return the sequence of actions that generated the given the node.
#

def get_path(node):
    
    path = []
    next_node = node
    while next_node[PARENT]:
        path.insert(0, next_node[ACTION])
        next_node = next_node[PARENT]
    return path


#
#   Create the root node of the search tree.
#

def create_root(initial_target, initial_robot, initial_boxes):
    
    return (((initial_target, initial_robot, initial_boxes), None, None, 0, []))


#
#   Evaluate whether the given node satisfies the goal of the problem.
#

def goal_test(node):

    return node[STATE][STATE_TARGET] == GOAL


#
#   Implement the node queuing function corresponding the breadth first search.
#

def queuing_fn_BreadthFS(queue, node):

    # add new node to end of queue for breadth first search
    return queue + [node]


#
#   This is an implementation of the General-Search algorithm
#   provided in the lecture notes to implement various search strategies.
#   The choice of search strategy is determined by the queuing function used.
#

def search(initial_target, initial_robot, initial_boxes):

    queue = [create_root(initial_target, initial_robot, initial_boxes)]
    nexpansions = 0
    while True:
        if queue == [] or nexpansions > MAX_EXPANSIONS:
            # no more possible states
            return None

        # expand next node in queue
        next_node = queue.pop(0)
        if goal_test(next_node):
            return next_node
        # create a new node for each valid action applied to next_node
        for action in ACTIONS:
            new_node = apply(action, next_node)
            # check if action is valid from current state
            if new_node[STATE][STATE_ROBOT] != next_node[STATE][STATE_ROBOT]:
                # since the robot has moved, the action was valid
                next_node[CHILDREN].append(new_node)
                queue = queuing_fn_BreadthFS(queue, new_node)


# solution = search((0,1), (0,1), ((1,2), (1,3))); get_path(solution)
# ['LIFT_LEFT']
# solution = search((1,1), (1,1), ((1,2), (1,3))); get_path(solution)
# ['LIFT_UP', 'LIFT_LEFT']
# solution = search((1,1), (1,1), ((1,0), (1,3))); get_path(solution)
# ['LIFT_UP', 'LIFT_LEFT']
# solution = search((1,1), (1,1), ((0,1), (1,3))); get_path(solution)
# ['LIFT_LEFT', 'LIFT_UP']
# solution = search((1,0), (1,1), ((0,1), (1,3))); get_path(solution)
# ['LEFT', 'LIFT_UP']
# solution = search((1,0), (1,1), ((0,0), (1,3))); get_path(solution)
# ['UP', 'LEFT', 'LIFT_RIGHT', 'DOWN', 'LEFT', 'LIFT_UP']
# solution = search((1,0), (1,1), ((0,0),(0,1))); get_path(solution)
# ['UP', 'LIFT_DOWN', 'UP', 'LEFT', 'LIFT_RIGHT', 'DOWN', 'LEFT', 'LIFT_UP']


# create_root((1,1), (2,2), ((1,2), (1,3)))
# node1 = apply('LEFT', root)
# node2 = apply('UP', node1)
# get_path(root)  # []
# get_path(node1)  # ['LEFT']
# get_path(node2)  # ['LEFT', 'UP']

# node1 = create_root((1,1), (2,1), ())
# node2 = apply('UP', node1)
