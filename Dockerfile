FROM alpine:3.14
RUN apk update \
&& apk add libwebp-tools sqlite python3 bash py3-pip vim zip curl
ENTRYPOINT ["/bin/bash"]
