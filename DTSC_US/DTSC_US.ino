/*
 * Author: Joey Broussard
 * PNI, 20200812
 * 
 * Control of the stepper motor performed on dedicated arduino
 * for the Delayed Tactile Startle Conditioning paradigm. Designed for 
 * master Arduino to activate interrupt input on the Arduino running
 * this sketch to generate the US. No specialized libraries are 
 * required as the motion of the US is controlled by an EasyDriver.
 * 
 * todo: 
 */

#include "Arduino.h"
#include <Wire.h>

//Pins
const int intPin = 2;//interrupt pin
const int slpPin = 9;//sleep pin, LOW = motor free
const int stepPin = 11;//step pin
const int dirPin = 12;//direction pin

//Cues for movement/direction
volatile long target = 5;//steps to rotate US forward
volatile long steps = 0;
const int smallAttack = 1;
const int medAttack = 3;
const int bigAttack = 5;//steps for big attack


void setup()
{ 
  //////////////////Pins/////////////////////////////////
  //Setup interrupt
  pinMode(intPin,INPUT);
  attachInterrupt(digitalPinToInterrupt(intPin),US,RISING);
  //Setup pin for deactivating the motor
  pinMode(slpPin,OUTPUT);
  digitalWrite(slpPin,HIGH);//HIGH = Motor in free run until receives commands
  //Direction pin changes direction of running
  pinMode(dirPin,OUTPUT);
  digitalWrite(dirPin,HIGH);
  //Step pin
  pinMode(stepPin,OUTPUT);
  digitalWrite(stepPin,LOW);
  
  /////////////////////Communication//////////////////////////
  //Initialize serial and report initial state
  Serial.begin(9600);
  Serial.println("Started, motor free");
  //Initialize I2C, declare event function
  Wire.begin(8);
  Wire.onReceive(receiveEvent);
}
/*Handling serial and I2C inputs*/
void commandIn(String str){
  if (str.length()==0){
    Serial.println("Couldn't parse");
  }
  if (str == "free"){
    digitalWrite(slpPin,HIGH);
    Serial.println("Motor free");
  }else if (str == "active"){
    digitalWrite(slpPin,LOW);
    Serial.println("Motor active");
  }
}
/*I2C event handler*/
void receiveEvent(int howMany){
  //Read the bytes off wire
  //First byte (0 = active/free, 1 = bigAttack val)
  //Second byte (0 = active/1, 1 = free/medAttack val, 2 = bigAttack)
  int state2change = Wire.read();
  int newStateVal = Wire.read();
  if (state2change == 0){
    if (newStateVal == 0) {
      commandIn("active");
    }else if (newStateVal == 1) {
      commandIn("free");
    }
  }else if (state2change == 1) {
    if (newStateVal == 0){
      target = smallAttack;
      Serial.println("Using small attack");
    }else if (newStateVal == 1){
      target = medAttack;
      Serial.println("Using medium attack");
    }else if (newStateVal == 2){
      target = bigAttack;
      Serial.println("Using big attack");
    }
  }
  //Finish emptying the wire if not yet done
  while (Wire.available()){
    Wire.read();
  }
}
/*US occurs on rising interrupt pin*/
void US()
{ 

  while (steps<target){
    digitalWrite(stepPin,HIGH);
    delayMicroseconds(1000);
    digitalWrite(stepPin,LOW);
    delayMicroseconds(1000);
    steps++;
  };
  steps = 0;
  digitalWrite(dirPin,!digitalRead(dirPin));

  while (steps<target){
    digitalWrite(stepPin,HIGH);
    delayMicroseconds(1000);
    digitalWrite(stepPin,LOW);
    delayMicroseconds(1000);
    steps++;
  };
  steps = 0;
  digitalWrite(dirPin,!digitalRead(dirPin));

  Serial.println("US done");
  
}

void loop(){
  //Wait for serial commands to dictate motor state
  if (Serial.available() > 0) {
    String inString = Serial.readStringUntil('\n');
    inString.replace("\n","");
    inString.replace("\r","");
    commandIn(inString);
  }
}
