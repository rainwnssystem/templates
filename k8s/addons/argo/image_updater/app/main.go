package main

import (
        "net/http"

        "github.com/gin-gonic/gin"
)

func main() {
        r := gin.Default()

        r.GET("/product", func(c *gin.Context) {
                c.String(http.StatusOK, "hello, product v1!")
        })

        r.GET("/healthz", func(c *gin.Context) {
                c.String(http.StatusOK, "ok")
        })

        r.Run()
}