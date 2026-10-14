// Bounded procedural Watch drawing, no JS runtime or image frames. AGPL-3.0-only.
#include "motion_draw.h"
#include "motion_config.h"
#include <algorithm>
#include <cmath>

namespace {
constexpr float pi=3.14159265359f;
struct Point {float x,y;};
Point safeCenter(float x,float y,float r){float d=hypotf(x,y),limit=std::max(0.f,216-r),a=d>limit?limit/d:1;return{x*a,y*a};}
uint16_t shade(float alpha){int v=lroundf(std::max(0.f,std::min(1.f,alpha))*255);return M5.Display.color565(v,v,v);}
// The painter measures the very same primitives before clearing their dirty union.
class Painter {
 public:
  Painter(bool measuring,float bob):measuring_(measuring){
   radius_=std::min(M5.Display.width(),M5.Display.height())*.5f-gork_motion_config::bodyInset;
   scale_=radius_/gork_motion_config::desktopHeadRadius;
   origin_={M5.Display.width()*.5f,M5.Display.height()*.5f+bob*scale_};
  }
  float scale()const{return scale_;}
  Point screen(float x,float y)const{return{origin_.x+x*scale_,origin_.y+y*scale_};}
  void include(Point p,float pad=1){left_=std::min(left_,p.x-pad);top_=std::min(top_,p.y-pad);right_=std::max(right_,p.x+pad);bottom_=std::max(bottom_,p.y+pad);valid_=true;}
  void line(Point a,Point b,float width,uint16_t color){
   include(a,width/2+2);include(b,width/2+2);
   if(measuring_)return;
   const float r=width/2;
   if(inside(a,r+1)&&inside(b,r+1)){M5.Display.drawWideLine(a.x,a.y,b.x,b.y,r,color);return;}
   // Boundary strokes use the same circular scan clip as filled paths.
   Point points[66];int n=0;float angle=atan2f(b.y-a.y,b.x-a.x);
   for(int i=0;i<=32;i++){float t=angle+pi/2+pi*i/32;points[n++]={a.x+cosf(t)*r,a.y+sinf(t)*r};}
   for(int i=0;i<=32;i++){float t=angle-pi/2+pi*i/32;points[n++]={b.x+cosf(t)*r,b.y+sinf(t)*r};}
   polygon(points,n,color);
  }
  void circle(Point p,float r,uint16_t color){
   include(p,r+2);if(measuring_)return;
   if(inside(p,r+1)){M5.Display.fillCircle(lroundf(p.x),lroundf(p.y),lroundf(r),color);return;}
   Point points[48];for(int i=0;i<48;i++){float t=2*pi*i/48;points[i]={p.x+cosf(t)*r,p.y+sinf(t)*r};}polygon(points,48,color);
  }
  void polygon(const Point* points,int count,uint16_t color){
   for(int i=0;i<count;i++)include(points[i],2);
   if(measuring_||count<3)return;
   float ymin=points[0].y,ymax=ymin;
   for(int i=1;i<count;i++){ymin=std::min(ymin,points[i].y);ymax=std::max(ymax,points[i].y);}
   for(int y=std::max(0,static_cast<int>(floorf(ymin)));y<=std::min(M5.Display.height()-1,static_cast<int>(ceilf(ymax)));y++){
    float dy=y-M5.Display.height()*.5f;
    if(fabsf(dy)>radius_)continue;
    const float half=sqrtf(std::max(0.f,radius_*radius_-dy*dy));
    const int clipLeft=static_cast<int>(ceilf(M5.Display.width()*.5f-half)),clipRight=static_cast<int>(floorf(M5.Display.width()*.5f+half));
    float intersections[192];int n=0;
    for(int i=0;i<count;i++){Point a=points[i],b=points[(i+1)%count];float scan=y+.5f;
     if((a.y<=scan&&b.y>scan)||(b.y<=scan&&a.y>scan))intersections[n++]=a.x+(scan-a.y)*(b.x-a.x)/(b.y-a.y);}
    std::sort(intersections,intersections+n);
    for(int i=0;i+1<n;i+=2){int x0=std::max(clipLeft,static_cast<int>(ceilf(intersections[i]))),x1=std::min(clipRight,static_cast<int>(floorf(intersections[i+1])));if(x1>=x0)M5.Display.drawFastHLine(x0,y,x1-x0+1,color);}
   }
  }
  GrokRenderer::Bounds bounds()const{
   if(!valid_)return {};
   int x=std::max(0,static_cast<int>(floorf(left_))),y=std::max(0,static_cast<int>(floorf(top_)));
   int right=std::min(M5.Display.width(),static_cast<int>(ceilf(right_))),bottom=std::min(M5.Display.height(),static_cast<int>(ceilf(bottom_)));
   return {static_cast<int16_t>(x),static_cast<int16_t>(y),static_cast<int16_t>(right-x),static_cast<int16_t>(bottom-y),true};
  }
 private:
  bool inside(Point p,float pad)const{return hypotf(p.x-M5.Display.width()*.5f,p.y-M5.Display.height()*.5f)+pad<=radius_;}
  bool measuring_,valid_=false;float radius_,scale_,left_=10000,top_=10000,right_=-10000,bottom_=-10000;Point origin_;
};

class Path {
 public:
  Path(Painter& painter,Point center,float scale,float angle):painter_(painter),center_(center),scale_(scale),c_(cosf(angle)),s_(sinf(angle)){}
  Point transform(float x,float y)const{return painter_.screen(center_.x+scale_*(x*c_-y*s_),center_.y+scale_*(x*s_+y*c_));}
  void begin(float x,float y){n_=0;point(x,y);}
  void point(float x,float y){last_={x,y};if(n_<192)points_[n_++]=transform(x,y);}
  void quad(float cx,float cy,float x,float y){Point a=last_;for(int i=1;i<=12;i++){float t=i/12.f,u=1-t;point(u*u*a.x+2*u*t*cx+t*t*x,u*u*a.y+2*u*t*cy+t*t*y);}}
  void cubic(float cx,float cy,float dx,float dy,float x,float y){Point a=last_;for(int i=1;i<=16;i++){float t=i/16.f,u=1-t;point(u*u*u*a.x+3*u*u*t*cx+3*u*t*t*dx+t*t*t*x,u*u*u*a.y+3*u*u*t*cy+3*u*t*t*dy+t*t*t*y);}}
  void fill(uint16_t color){painter_.polygon(points_,n_,color);}
  void stroke(float width,uint16_t color){for(int i=1;i<n_;i++)painter_.line(points_[i-1],points_[i],width*scale_*painter_.scale(),color);}
 private:
  Painter& painter_;Point center_,last_,points_[192];float scale_,c_,s_;int n_=0;
};

Point projectEye(float x,float y,float spacing,const MotionPose& p,float angle){
 float a=angle*pi/180,xx=x*cosf(a)-y*sinf(a),yy=x*sinf(a)+y*cosf(a);
 float sx=spacing+p.eyes[0]+xx,sy=p.eyes[1]+yy;
 float r=gork_motion_config::sphereRadius;
 float X=r*cosf(sy/r)*sinf(sx/r),Y=r*sinf(sy/r),Z=sqrtf(std::max(0.f,r*r-X*X-Y*Y));
 // Quaternion in the source is Rz * Rx * Ry: apply Y, then X, then Z.
 float yaw=p.eyes[8]*pi/180,pitch=p.eyes[7]*pi/180,roll=p.eyes[9]*pi/180;
 float x1=X*cosf(yaw)+Z*sinf(yaw),z1=-X*sinf(yaw)+Z*cosf(yaw);
 float y1=Y*cosf(pitch)-z1*sinf(pitch),z2=Y*sinf(pitch)+z1*cosf(pitch);
 float factor=gork_motion_config::cameraDistance/(gork_motion_config::cameraDistance-z2);
 float scale=gork_motion_config::eyeGeometryScale;
 return{(x1*cosf(roll)-y1*sinf(roll))*factor*scale,(x1*sinf(roll)+y1*cosf(roll))*factor*scale};
}
void eye(Painter& painter,const MotionPose& p,bool left){
 if(p.eyeAlpha<.002f)return;
 float width=p.eyes[left?3:5],height=p.eyes[left?4:6],r=std::min(width,height)/2;
 float x=width/2,y=height/2,spacing=(left?-1:1)*p.eyes[2]/2;
 Point points[192];int n=0;
 auto push=[&](float px,float py){Point projected=projectEye(px,py,spacing,p,left?p.leftAngle:p.rightAngle);points[n++]=painter.screen(projected.x,projected.y);};
 auto edge=[&](float ax,float ay,float bx,float by){int steps=std::max(2,static_cast<int>(ceilf(hypotf(bx-ax,by-ay)/1.5f)));for(int i=0;i<steps;i++)push(ax+(bx-ax)*i/steps,ay+(by-ay)*i/steps);};
 auto corner=[&](float cx,float cy,float angle){for(int i=0;i<14;i++){float a=angle+i/14.f*pi/2;push(cx+cosf(a)*r,cy+sinf(a)*r);}};
 edge(-x+r,-y,x-r,-y);corner(x-r,-y+r,-pi/2);edge(x,-y+r,x,y-r);corner(x-r,y-r,0);edge(x-r,y,-x+r,y);corner(-x+r,y-r,pi/2);edge(-x,y-r,-x,-y+r);corner(-x+r,-y+r,pi);
 painter.polygon(points,n,shade(p.eyeAlpha));
}
void pen(Painter& painter,const MotionPose& p,Point center,float scale){
 float a=p.penRotation,c=cosf(a),s=sinf(a);Point nib={center.x+p.penX*scale,center.y+(p.penY-35)*scale};
 Path path(painter,nib,scale*p.penSize,a);uint16_t white=shade(p.pen);
 int style=lroundf(p.penStyle);
 if(style==0){path.begin(0,0);path.quad(-1,-24,4,-44);path.quad(11,-77,35,-102);path.cubic(43,-76,33,-40,6,-24);path.quad(2,-10,0,0);path.fill(white);
  path.begin(5,-26);path.quad(17,-61,32,-91);path.stroke(2.6f,TFT_BLACK);
  for(auto pair:{0,1,2}){const float v[][4]={{13,-46,30,-53},{19,-61,34,-69},{8,-31,21,-35}};path.begin(v[pair][0],v[pair][1]);path.point(v[pair][2],v[pair][3]);path.stroke(2.6f,TFT_BLACK);}}
 else if(style==1){path.begin(0,0);path.point(-20,-43);path.point(-12,-79);path.point(12,-79);path.point(20,-43);path.fill(white);path.begin(0,-2);path.point(0,-38);path.stroke(3,TFT_BLACK);Point dot=path.transform(0,-43);painter.circle(dot,5*scale*p.penSize*painter.scale(),TFT_BLACK);path.begin(-16,-66);path.point(16,-66);path.stroke(3,TFT_BLACK);}
 else if(style==2){path.begin(0,0);path.point(-7,-17);path.point(-7,-88);path.quad(-7,-93,0,-93);path.quad(7,-93,7,-88);path.point(7,-17);path.fill(white);for(float y:{-19.f,-78.f}){path.begin(-7,y);path.point(7,y);path.stroke(2,TFT_BLACK);}}
 else{path.begin(0,0);path.cubic(-20,-14,-17,-32,-8,-44);path.point(8,-44);path.cubic(17,-30,14,-10,0,0);path.fill(white);path.begin(-5,-48);path.point(-3,-94);path.quad(0,-103,3,-94);path.point(5,-48);path.fill(white);path.begin(0,-3);path.quad(8,-17,5,-34);path.stroke(2,TFT_BLACK);}
 (void)c;(void)s;
}
void paintAll(Painter& painter,const MotionPose& p){
 eye(painter,p,true);eye(painter,p,false);
 if(p.spinner>.002f){Point center=safeCenter(p.spinX,p.spinY,38*p.spinScale);float scale=(.4f+.6f*p.spinner)*p.spinScale;Path path(painter,center,scale,p.spinAngle);
  for(int segment=0;segment<2;segment++){float start=segment==0?-.6f*pi:.98f*pi,end=segment==0?.82f*pi:1.12f*pi;path.begin(32*cosf(start),32*sinf(start));for(int i=1;i<=60;i++){float a=start+(end-start)*i/60;path.point(32*cosf(a),32*sinf(a));}path.stroke(9,shade(p.spinner));}}
 if(p.paper>.001f||p.pen>.001f){float scale=.78f*p.writeScale;Point center=safeCenter(p.writeX,p.writeY,190*scale);float cursor=std::min(2.999999f,p.ink*3);int line=static_cast<int>(floorf(cursor));float drawn=std::min(1.f,(cursor-line)/.83f);
  Path ink(painter,{center.x,center.y-35*scale},scale,0);
  auto yAt=[](int n,float x){return 34+n*30+sinf((x+90)*.12f)*3.5f+sinf((x+90)*.34f)*1.8f;};
  for(int n=0;n<=line;n++){float fraction=n<line?1:drawn;if(fraction<=0)continue;float end=-90+170*fraction;ink.begin(-90,yAt(n,-90));for(float x=-88;x<end;x+=2)ink.point(x,yAt(n,x));ink.point(end,yAt(n,end));ink.stroke(p.strokeWidth,shade(p.paper));}
  pen(painter,p,center,scale);}
 if(p.question>.002f){float scale=p.questionScale*p.question*p.qSize;Point center=safeCenter(p.qX,p.qY+p.questionY,63*std::max(1.f,p.questionScale)*p.qSize);Path path(painter,center,scale,-.10f);path.begin(-23,-21);path.cubic(-21,-47,23,-48,23,-21);path.cubic(23,-5,0,-4,0,14);path.stroke(13,shade(p.question));painter.circle(path.transform(0,37),7*scale*painter.scale(),shade(p.question));}
}
} // namespace

GrokRenderer::Bounds MotionDraw::bounds(const MotionPose& pose){Painter painter(true,pose.bob);paintAll(painter,pose);return painter.bounds();}
void MotionDraw::draw(const MotionPose& pose){Painter painter(false,pose.bob);paintAll(painter,pose);}
