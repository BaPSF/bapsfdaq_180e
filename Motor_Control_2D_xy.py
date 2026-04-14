'''
Motor_Control_2D controls two motors (x and y), using Single_Motor_Control
In this case, the x motor moves in x direction and y motor moves in y direction.

Modified by: Yuchen Qian
Oct 2017
'''

import math
import numpy
import time

from Single_Motor_Control import Motor_Control

#############################################################################################
#############################################################################################


class Motor_Control_2D:

    def __init__(self, x_ip_addr = None, y_ip_addr = None):

        self.x_mc = Motor_Control(verbose=True, server_ip_addr= x_ip_addr)
        self.y_mc = Motor_Control(verbose=True, server_ip_addr= y_ip_addr)


        self.steps_per_cm = 200000.0 # For EG=20000steps/rev motor and 1mm/rev shaft
        # self.steps_per_degree = 33333.0

        self.motor_moving = False

        self.d_outside = 71.0 #cm distance from the ball valve to the motor's motion channel
        self.d_inside = 35.5 #cm distance from the ball valve to the center of the chamber (0,0) point



    def set_steps_per_rev(self, xsteps, ysteps):
        # Set up the steps per revolution
        self.x_mc.steps_per_rev(xsteps)
        self.y_mc.steps_per_rev(ysteps)

    # Translate the input cartesian positions to motor positions. Here the distance from the ball valve to
    # the motor's motion channel is 29.5 inch (75cm), and the distance from the ball valve to the center of
    # the chamber (0,0) is approximately 14 inch (35.5cm)
    def translate_to_motor_coordinate(self, dx, dy): #dx, dy is the user input coordinate. mx, my is the motor coordinate.
        my = self.d_outside * dy / (dx + self.d_inside)
        mx = numpy.sqrt(dy**2 + (dx + self.d_inside)**2) - self.d_inside
        print('for test: move to motor coordinate', mx, my)
        return mx, my

    def translate_to_user_coordinate(self, mx, my):
        dx = numpy.sqrt((mx + self.d_inside)**2 / ((my / self.d_outside)**2 + 1)) - self.d_inside
        dy = my * (dx + self.d_inside) / self.d_outside
        return dx, dy

    def move_to_position(self, x_pos, y_pos):
        # Directly move the motor to their absolute position
        #mx_pos, my_pos = self.translate_to_motor_coordinate(x_pos, y_pos)
        x_step = self.cm_to_steps(x_pos)
        y_step = self.cm_to_steps(y_pos)
        self.x_mc.set_position(x_step)
        self.y_mc.set_position(y_step)
        self.motor_moving = True
        self.wait_for_motion_complete()


#--------------------------------------------------------------------------------------------------


    def stop_now(self):
        # Stop motor movement now
        self.x_mc.stop_now()
        self.y_mc.stop_now()


    def set_zero(self):
        self.x_mc.set_zero()
        self.y_mc.set_zero()


    def reset_motor(self):
        self.x_mc.reset_motor()
        self.y_mc.reset_motor()


#--------------------------------------------------------------------------------------------------


    def ask_velocity(self):
        self.speedx = self.x_mc.motor_velocity()
        self.speedy = self.y_mc.motor_velocity()
        return self.speedx, self.speedy

    def set_velocity(self, vx, vy):
        self.x_mc.set_speed(vx)
        self.y_mc.set_speed(vy)


#-------------------------------------------------------------------------------------------



    def cm_to_steps(self, d:float) -> int:
        # convert distance d in cm to motor position
        return int(d * self.steps_per_cm)

    # def degree_to_steps(self, d:float) -> int: # This feature applies to Z-Th probe drive
    # 	# convert angle d in degree to motor position
    # 	return int(d * self.steps_per_degree)

#-------------------------------------------------------------------------------------------



    def current_probe_position(self):
        # Obtain encoder feedback and calculate probe position
        """ Might need a encoder_unit_per_step, if encoder feedback != input step """
        mx_pos = self.x_mc.current_position() / self.steps_per_cm *5
        my_pos = self.y_mc.current_position() / self.steps_per_cm *5 #Seems that 1 encoder unit = 5 motor step unit
        #dx_pos, dy_pos = self.translate_to_user_coordinate(mx_pos,my_pos)

        return mx_pos, my_pos


#-------------------------------------------------------------------------------------------


    def wait_for_motion_complete(self):

        timeout = time.time() + 300

        while True :

            x_stat = self.x_mc.check_status()
            y_stat = self.y_mc.check_status()
            time.sleep(0.2)

            x_not_moving = x_stat.find('M') == -1
            y_not_moving = y_stat.find('M') == -1


#				print ('x:', x_stat)
#				print ('y:', y_stat)
#				print ('z:', z_stat)
#				print (x_not_moving, y_not_moving, z_not_moving)

            if x_not_moving and y_not_moving:
                break
            elif time.time() > timeout:
                raise TimeoutError("Motor has been moving for over 5min???")
        self.motor_moving = False
        print ("Motor stopped")


#-------------------------------------------------------------------------------------------


    def disable(self):
        self.x_mc.inhibit()
        self.y_mc.inhibit()

    def enable(self):
        self.x_mc.enable()
        self.y_mc.enable()

    def set_input_usage(self, usage):
        self.x_mc.set_input_usage(usage)
        self.y_mc.set_input_usage(usage)

    def sdsdsdsds(self):
        self.x_mc.sdsdsdsds()
        self.y_mc.sdsdsdsds()



########################################################################################################
# standalone testing:

if __name__ == '__main__':
    pass
    # mc = Motor_Control_2D(x_ip_addr = "192.168.0.50", y_ip_addr = "192.168.0.40")
    # mc.current_probe_position()
    # mc.reset_motor()
#	mc.move_to_position(0,0,0)
#	mc.move(0,0,0)
#	print (mc.motor_to_probe)
#	mc.set_zero()

#	mc.calculate_motor(-5,5,-11)
