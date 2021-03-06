from maddpg import MaDDPG
import numpy as np
from maddpg import MaDDPG
import numpy as np
state_dim = 3
action_dim =2
num_agents = 4


maddpg  = MaDDPG(num_agents,state_dim,action_dim)

for ii in range(1000):
    state =np.random.rand(num_agents,state_dim)
    next_state =np.random.rand(num_agents,state_dim)
    action = np.random.rand(num_agents, action_dim)
    reward = np.random.rand(num_agents)
    done = 0
    maddpg.perceive(state,action,reward, next_state,done)

maddpg.close_session()
