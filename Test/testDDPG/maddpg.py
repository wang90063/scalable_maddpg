import tensorflow as tf
import numpy as np
from actor_network import ActorNetwork
from criticnetwork import CriticNetwork
from ou_noise import OUNoise
from replay_buffer import ReplayBuffer

STATE_DIM = 3
ACTION_DIM =2
GAMMA = 0.99
BATCH_SIZE = 64

REPLAY_BUFFER_SIZE = 1000000
REPLAY_START_SIZE = 1000
SAVE_STEPS = 100
class MaDDPG:
    def __init__(self,num_agents,state_dim,action_dim):
        self.time_step = 0
        self.sess = tf.InteractiveSession()
        self.num_agents = num_agents
        self.state_dim = STATE_DIM
        self.action_dim = ACTION_DIM
        self.agents = self.create_multi_agents(self.sess,num_agents,self.state_dim,self.action_dim)
        self.critic = CriticNetwork(self.sess,state_dim,action_dim)
        self.exploration_noise = OUNoise((self.num_agents,action_dim))
        self.replay_buffer = ReplayBuffer(REPLAY_BUFFER_SIZE)
        # for store checkpoint
        self.saver = tf.train.Saver()

    def train(self):
        minibatch = self.replay_buffer.get_batch(BATCH_SIZE)
        state_batch = np.zeros((BATCH_SIZE,self.num_agents,self.state_dim))
        action_batch = np.zeros((BATCH_SIZE,self.num_agents,self.action_dim))
        reward_batch = np.zeros((BATCH_SIZE,self.num_agents))
        next_state_batch = np.zeros((BATCH_SIZE,self.num_agents,self.state_dim))
        done_batch = np.zeros((BATCH_SIZE))
        for ii in range(BATCH_SIZE):
            state_batch[ii,:,:] = minibatch[ii][0]
            action_batch[ii,:,:] = minibatch[ii][1]
            reward_batch[ii,:]  = minibatch[ii][2]
            next_state_batch[ii,:,:] = minibatch[ii][3]
            done_batch[ii] = minibatch[ii][4]

        # calculate Gt batch
        next_action_batch = self.target_actions(next_state_batch)
        q_value_batch = self.critic.target_q(next_state_batch,next_action_batch)
        gt = np.zeros((BATCH_SIZE,self.num_agents))
        for ii in range(BATCH_SIZE):
            if done_batch[ii]:
                gt[ii,:] = reward_batch[ii,:]
            else:
                gt[ii,:] = reward_batch[ii,:] + GAMMA*q_value_batch[ii,:]
        #update critic by minimizing the loss
        self.critic.train(gt,state_batch,action_batch)

        # update policy using the sampling gradients
        q_gradients_batch = self.critic.gradients(state_batch,action_batch)
        self.train_agents(q_gradients_batch,state_batch)

        # update target network
        self.critic.update_target()


    def update_agents_target(self):
        for agent in self.agents:
            agent.update_target()

    def train_agents(self,gradients_batch,state_batch):
        # gradients_batch = [batchsize* agents* action_dim]
        # state_batch = [batchsize* agents * state_dim ]
        for ii in range(self.num_agents):
            grad = gradients_batch[:,ii,:]
            state = state_batch[:,ii,:]
            self.agents[ii].train(grad,state)



    def create_multi_agents(self,sess, num_agents, state_dim, action_dim):
        agents =[]
        nets = None
        for ii in range(num_agents):
            agent_name = 'agent'+str(ii)
            agents.append(ActorNetwork(sess,state_dim, action_dim, agent_name,nets))
            nets = agents[-1].nets
        return agents

    def add_agents(self,add_num):
        for ii in range(add_num):
            self.num_agents+=1

            agent_name = 'agent'+ str(self.num_agents)
            self.agents.append(ActorNetwork(self.sess,self.state_dim,self.action_dim,
                                            agent_name, self.agents[-1].nets))
        # if add a new agent then reset the noise and replay buffer
        self.exploration_noise = OUNoise((self.num_agents, self.action_dim))
        self.replay_buffer = ReplayBuffer(REPLAY_BUFFER_SIZE)


    def action(self,state): # here is action, for one state on agent, not batch_sized actions
        # state = [num_agents * state_dim]
        # actions = [num_agents *  action_dim]
        action = np.zeros((self.num_agents,self.action_dim))
        for ii in range(self.num_agents):
            action[ii,:] = self.agents[ii].action(state[ii,:])
        return action

    def target_actions(self,state_batch):
        # the state size  is batch_size* num_agents * state_dimension
        actions = np.zeros((state_batch.shape[0],self.num_agents,self.action_dim))
        for ii in range(self.num_agents):
            actions[:,ii,:] = self.agents[ii].actions(state_batch[:,ii,:])
        return  actions

    def noise_action(self,state):
        action = self.action(state)
        return action+ self.exploration_noise.noise()

    def close_session(self):
        self.sess.close()

    def perceive(self,state,action,reward,next_state,done):
        # store {st,at,Rt+1,st+1}
        self.replay_buffer.add(state,action,reward,next_state,done)

        if self.replay_buffer.count() > REPLAY_START_SIZE:
            self.time_step += 1
            self.train()
            if self.time_step%SAVE_STEPS==0:
                self.save_network()
            # if self.time_step % 10000 == 0:
            # self.actor_network.save_network(self.time_step)
            # self.critic_network.save_network(self.time_step)

            # Re-iniitialize the random process when an episode ends
        if done:
            self.exploration_noise.reset()

    def load_network(self):
        checkpoint = tf.train.get_checkpoint_state("saved_network")
        if checkpoint and checkpoint.model_checkpoint_path:
            self.saver.restore(self.sess, checkpoint.model_checkpoint_path)
            print("Successfully loaded:", checkpoint.model_checkpoint_path)
        else:
            print('Could not find old network weights')

    def save_network(self):
        # do not processing under Dropbox or  exit drop box and then run
        print('save network...',self.time_step)
        self.saver.save(self.sess, 'saved_network/' + 'network', global_step=self.time_step)