#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""GRU-CTC model."""

import tensorflow as tf
from .ctc_base import ctcBase


class GRU_CTC(ctcBase):
    """GRU-CTC model.
    Args:
        batch_size: int, batch size of mini batch
        input_size: int, the dimensions of input vectors
        num_cell: int, the number of memory cells in each layer
        num_layer: int, the number of layers
        output_size: int, the number of nodes in softmax layer (except for blank class)
        parameter_init: A float value. Range of uniform distribution to initialize weight parameters
        clip_gradients: A float value. Range of gradient clipping (non-negative)
        clip_activation: A float value. Range of activation clipping (non-negative)
        dropout_ratio_input: A float value. Dropout ratio in input-hidden layers
        dropout_ratio_hidden: A float value. Dropout ratio in hidden-hidden layers
        num_proj: int, the number of nodes in recurrent projection layer
        weight_decay: A float value. Regularization parameter for weight decay
        bottleneck_dim: not used
    """

    def __init__(self,
                 batch_size,
                 input_size,
                 num_cell,
                 num_layer,
                 output_size,
                 parameter_init=0.1,
                 clip_gradients=None,
                 clip_activation=None,
                 dropout_ratio_input=1.0,
                 dropout_ratio_hidden=1.0,
                 num_proj=None,
                 weight_decay=0.0,
                 bottleneck_dim=None):

        ctcBase.__init__(self, batch_size, input_size, num_cell, num_layer,
                         output_size, parameter_init,
                         clip_gradients, clip_activation,
                         dropout_ratio_input, dropout_ratio_hidden,
                         weight_decay)

        self.num_proj = None

    def define(self):
        """Construct network."""
        # Generate placeholders
        self._generate_pl()

        # Dropout for Input
        self.inputs = tf.nn.dropout(self.inputs_pl,
                                    self.keep_prob_input_pl,
                                    name='dropout_input')

        gru_list = []
        for i_layer in range(self.num_layer):
            with tf.name_scope('GRU_hidden' + str(i_layer + 1)):

                initializer = tf.random_uniform_initializer(minval=-self.parameter_init,
                                                            maxval=self.parameter_init)

                with tf.variable_scope('GRU', initializer=initializer):
                    gru = tf.contrib.rnn.GRUCell(self.num_cell)

                # Dropout (output)
                gru = tf.contrib.rnn.DropoutWrapper(
                    gru, output_keep_prob=self.keep_prob_hidden_pl)

                gru_list.append(gru)

        # Stack multiple cells
        stacked_gru = tf.contrib.rnn.MultiRNNCell(
            gru_list, state_is_tuple=True)

        # Ignore 2nd return (the last state)
        outputs, _ = tf.nn.dynamic_rnn(cell=stacked_gru,
                                       inputs=self.inputs,
                                       sequence_length=self.seq_len_pl,
                                       dtype=tf.float32)

        # (batch_size, max_timesteps, input_size_splice)
        inputs_shape = tf.shape(self.inputs_pl)
        batch_size, max_timesteps = inputs_shape[0], inputs_shape[1]

        # Reshape to apply the same weights over the timesteps
        outputs = tf.reshape(outputs, shape=[-1, self.num_cell])

        with tf.name_scope('output'):
            # Affine
            W_output = tf.Variable(tf.truncated_normal(shape=[self.num_cell, self.num_classes],
                                                       stddev=0.1, name='W_output'))
            b_output = tf.Variable(
                tf.zeros(shape=[self.num_classes], name='b_output'))
            logits_2d = tf.matmul(outputs, W_output) + b_output

            # Reshape back to the original shape
            logits_3d = tf.reshape(
                logits_2d, shape=[batch_size, -1, self.num_classes])

            # Convert to (max_timesteps, batch_size, num_classes)
            self.logits = tf.transpose(logits_3d, (1, 0, 2))
