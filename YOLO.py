# *******************************************************************
#
# Author : Thanh Nguyen, 2018
# Email  : sthanhng@gmail.com
# Github : https://github.com/sthanhng
#
# Face detection using the YOLOv3 algorithm
#
# Description : YOLO.py
# Contains methods of YOLO
#
# *******************************************************************

import os
import colorsys
import numpy as np

from yolo.model import eval
from yolo.utils import letterbox_image

from keras import backend as K
from keras.models import load_model
from timeit import default_timer as timer
from PIL import ImageDraw


class YOLO(object):
    def __init__(self, args):
        self.args = args
        self.model_path = args.model
        self.classes_path = args.classes
        self.anchors_path = args.anchors
        self.class_names = self._get_class()
        self.anchors = self._get_anchors()
        self.sess = K.get_session()
        self.boxes, self.scores, self.classes = self._generate()
        self.model_image_size = args.img_size

    def _get_class(self):
        classes_path = os.path.expanduser(self.classes_path)
        with open(classes_path) as f:
            class_names = f.readlines()
        class_names = [c.strip() for c in class_names]
        print(class_names)
        return class_names

    def _get_anchors(self):
        anchors_path = os.path.expanduser(self.anchors_path)
        with open(anchors_path) as f:
            anchors = f.readline()
        anchors = [float(x) for x in anchors.split(',')]
        return np.array(anchors).reshape(-1, 2)

    def _generate(self):
        model_path = os.path.expanduser(self.model_path)
        assert model_path.endswith(
            '.h5'), 'Keras model or weights must be a .h5 file'

        # Load model, or construct model and load weights
        num_anchors = len(self.anchors)
        num_classes = len(self.class_names)
        try:
            self.yolo_model = load_model(model_path, compile=False)
        except:
            # make sure model, anchors and classes match
            self.yolo_model.load_weights(self.model_path)
        else:
            assert self.yolo_model.layers[-1].output_shape[-1] == \
                   num_anchors / len(self.yolo_model.output) * (
                           num_classes + 5), \
                'Mismatch between model and given anchor and class sizes'

        print(
            '[i] ==> {} model, anchors, and classes loaded.'.format(model_path))

        # Generate colors for drawing bounding boxes
        hsv_tuples = [(x / len(self.class_names), 1., 1.)
                      for x in range(len(self.class_names))]
        self.colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        self.colors = list(
            map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)),
                self.colors))

        # Shuffle colors to decorrelate adjacent classes.
        np.random.seed(102)
        np.random.shuffle(self.colors)
        np.random.seed(None)

        # Generate output tensor targets for filtered bounding boxes.
        self.input_image_shape = K.placeholder(shape=(2,))
        boxes, scores, classes = eval(self.yolo_model.output, self.anchors,
                                           len(self.class_names),
                                           self.input_image_shape,
                                           score_threshold=self.args.score,
                                           iou_threshold=self.args.iou)
        return boxes, scores, classes

    def detect_image(self, image):
        start_time = timer()

        if self.model_image_size != (None, None):
            assert self.model_image_size[
                       0] % 32 == 0, 'Multiples of 32 required'
            assert self.model_image_size[
                       1] % 32 == 0, 'Multiples of 32 required'
            boxed_image = letterbox_image(image, tuple(
                reversed(self.model_image_size)))
        else:
            new_image_size = (image.width - (image.width % 32),
                              image.height - (image.height % 32))
            boxed_image = letterbox_image(image, new_image_size)
        image_data = np.array(boxed_image, dtype='float32')

        print(image_data.shape)
        image_data /= 255.
        # Add batch dimension
        image_data = np.expand_dims(image_data, 0)

        out_boxes, out_scores, out_classes = self.sess.run(
            [self.boxes, self.scores, self.classes],
            feed_dict={
                self.yolo_model.input: image_data,
                self.input_image_shape: [image.size[1], image.size[0]],
                K.learning_phase(): 0
            })

        print('[i] ==> Found {} face(s) for this image'.format(len(out_boxes)))
        thickness = (image.size[0] + image.size[1]) // 400

        for i, c in reversed(list(enumerate(out_classes))):
            predicted_class = self.class_names[c]
            box = out_boxes[i]
            score = out_scores[i]

            text = '{} {:.2f}'.format(predicted_class, score)
            draw = ImageDraw.Draw(image)

            top, left, bottom, right = box
            top = max(0, np.floor(top + 0.5).astype('int32'))
            left = max(0, np.floor(left + 0.5).astype('int32'))
            bottom = min(image.size[1], np.floor(bottom + 0.5).astype('int32'))
            right = min(image.size[0], np.floor(right + 0.5).astype('int32'))

            print(text, (left, top), (right, bottom))

            for thk in range(thickness):
                draw.rectangle(
                    [left + thk, top + thk, right - thk, bottom - thk],
                    outline=self.colors[c])
            del draw

        end_time = timer()
        print('[i] ==> Processing time: {:.2f}ms'.format((end_time -
                                                          start_time) * 1000))
        return image

    def close_session(self):
        self.sess.close()
