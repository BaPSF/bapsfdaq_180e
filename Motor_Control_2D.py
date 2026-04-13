'''
Motor_Control_2D controls two motors (x and y), using Single_Motor_Control
In this case, the x motor moves in axial direction and y motor moves in theta direction.

Modified by: Yuchen Qian
Oct 2017
'''

import math
from Single_Motor_Control import Motor_Control
import time
import numpy


#############################################################################################
#############################################################################################


class Motor_Control_2D:

    def __init__(self, x_ip_addr = None, y_ip_addr = None):

        self.x_mc = Motor_Control(verbose=True, server_ip_addr= x_ip_addr)
        self.y_mc = Motor_Control(verbose=True, server_ip_addr= y_ip_addr)


        self.steps_per_cm = 31532.0
        self.steps_per_degree = 33333.0





    def move_to_position(self, x_pos, y_pos):
        # Directly move the motor to their absolute position
        x_step = self.cm_to_steps(x_pos)
        y_step = self.degree_to_steps(y_pos)
        self.x_mc.set_position(x_step)
        self.y_mc.set_position(y_step)

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

    def degree_to_steps(self, d:float) -> int:
        # convert angle d in degree to motor position
        return int(d * self.steps_per_degree)

#-------------------------------------------------------------------------------------------



    def current_probe_position(self):
        # Obtain encoder feedback and calculate probe position
        """ Might need a encoder_unit_per_step, if encoder feedback != input step """
        x_position = self.x_mc.current_position() / self.steps_per_cm
        y_position = self.y_mc.current_position() / self.steps_per_degree *5 #Seems that 1 encoder unit = 5 motor step unit

        return x_position, y_position


#-------------------------------------------------------------------------------------------

    def check_status(self):

        x_stat = self.x_mc.check_status()
        y_stat = self.y_mc.check_status()

        return x_stat, y_stat

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

        print ("Motor stopped")


#-------------------------------------------------------------------------------------------


    def disable(self):
        #self.x_mc.inhibit()
        self.y_mc.inhibit()

    def enable(self):
        #self.x_mc.enable()
        self.y_mc.enable()

    def set_input_usage(self, usage):
        self.x_mc.set_input_usage(usage)
        #self.y_mc.set_input_usage(usage)

    def clear_alarm(self):
        self.x_mc.clear_alarm()
        self.y_mc.clear_alarm()


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
